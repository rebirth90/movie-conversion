#!/usr/bin/env python3
import logging
import time
import signal
import glob
from pathlib import Path
from config import AppConfig
from db_utils import DatabaseManager
from file_utils import should_process_path, validate_target_root
from logging_utils import start_job_logging, restore_main_logging
from email_utils import send_failure_email
from models import MediaType, MediaFactory, JobStatus, JobContext
from exceptions import MediaValidationError, ShutdownRequestedError
from encoding_utils import IntelQSVStrategy
from conversion_utils import ProcessingPipeline
import threading

logger = logging.getLogger(__name__)

def queue_worker_loop(config: AppConfig, shutdown_event: threading.Event, poll_interval: int = 60) -> None:

    db = DatabaseManager(config.db_path)

    logger.info("="*80)
    logger.info("ENTERPRISE QUEUE WORKER STARTED")
    logger.info(f"SQLite DB: {db.db_path}")
    logger.info(f"Poll_interval: {poll_interval}s")
    logger.info("="*80)
    logger.info("="*80)
    
    last_reset_time = 0

    while not shutdown_event.is_set():
        try:
            if not validate_target_root(config.base_movies_root) or not validate_target_root(config.base_tvseries_root):
                logger.critical("Both source roots are inaccessible. Waiting for mount...")
                shutdown_event.wait(60)
                continue
                
            if not validate_target_root(config.target_movies_dir) or not validate_target_root(config.target_tvseries_dir):
                logger.critical("Archive targets are inaccessible. Sleeping 60s...")
                shutdown_event.wait(60)
                continue

            current_time = time.time()
            if current_time - last_reset_time > 300: # 5 minutes
                db.reset_orphaned_jobs()
                db.cleanup_old_jobs(days=30)
                last_reset_time = current_time
                
            db.ingest_text_queue(config.queue_file)
            job_record = db.dequeue_pending_job()

            if job_record:
                job_id, job_path_str = job_record
                logger.info(f"DEQUEUED_JOB [{job_id}]: {job_path_str}")
                job_path = Path(job_path_str)

                # ===== SAFEGUARD: REJECT SEEDING PATHS =====
                if not should_process_path(job_path):
                    db.update_job_status(job_id, JobStatus.REJECTED.value)
                    continue
                # ===== END SAFEGUARD =====

                # ===== MEDIA TYPE IDENTIFICATION =====
                job_path_abs_str = str(job_path.absolute())
                media_type = MediaType.UNKNOWN
                
                if job_path_abs_str.startswith(str(config.base_movies_root)):
                    media_type = MediaType.MOVIE
                elif job_path_abs_str.startswith(str(config.base_tvseries_root)):
                    media_type = MediaType.TVSERIES
                    
                # Instantiate MediaItem Domain Models via Factory
                try:
                    media_items = MediaFactory.create(media_type, job_path, config)
                except MediaValidationError as e:
                    logger.error(f"Media validation error for {job_path}: {e}")
                    db.update_job_status(job_id, JobStatus.REJECTED.value)
                    continue
                except ValueError as e:
                    logger.warning(f"Skipping invalid media file {job_path}: {e}")
                    db.update_job_status(job_id, JobStatus.REJECTED.value)
                    continue
                     
                if not media_items:
                     logger.error(f"Failed to resolve domain model for {job_path}")
                     db.update_job_status(job_id, JobStatus.REJECTED.value)
                     continue

                all_successful = True
                shutdown_requested = False
                
                for media_item in media_items:
                    log_name = media_item.clean_name()
                    
                    # Start per-job logging
                    general_log_path = start_job_logging(config, log_name)
                    
                    try:
                        # Assemble Context, Strategy and Pipeline
                        strategy = IntelQSVStrategy(config)
                        context = JobContext(config=config, db=db, media_item=media_item, strategy=strategy, job_id=job_id, shutdown_event=shutdown_event)
                        pipeline = ProcessingPipeline(context)
                        
                        # Execute
                        result = pipeline.run()
                        if not result:
                            logger.error(f"Pipeline returned False/failed for {media_item.source_path}, moving on.")
                            all_successful = False
                                
                    except ShutdownRequestedError:
                        logger.info(f"JOB_SUSPENDED: {media_item.source_path} will be automatically requeued on next boot.")
                        shutdown_requested = True
                        break
                    except Exception as e:
                        logger.exception(f"ERROR_in_job_processing: {e}")
                        all_successful = False
                        
                        # Attempt to send failure email
                        try:
                            attachments = []
                            if general_log_path and general_log_path.exists():
                                attachments.append(general_log_path)
                            
                            if config.log_ffmpeg_dir.exists():
                                safe_log_name = glob.escape(log_name)
                                candidates = list(config.log_ffmpeg_dir.glob(f"*{safe_log_name}*.log"))
                                if candidates:
                                    newest_ffmpeg_log = max(candidates, key=lambda p: p.stat().st_mtime)
                                    attachments.append(newest_ffmpeg_log)
                            
                            send_failure_email(
                                config=config,
                                subject=f"Conversion Failed for {log_name}",
                                body=f"The conversion job for '{media_item.source_path}' failed.\n\nError: {e}\n\nSee attached logs for details.",
                                attachment_paths=attachments
                            )
                        except Exception as email_err:
                            logger.error(f"Failed to send failure email: {email_err}")
                    finally:
                        # Restore logging to main file
                        restore_main_logging()

                if shutdown_requested:
                    db.update_job_status(job_id, JobStatus.PENDING.value)
                elif all_successful:
                    db.update_job_status(job_id, JobStatus.COMPLETED.value)
                else:
                    db.update_job_status(job_id, JobStatus.FAILED.value)

            else:
                shutdown_event.wait(poll_interval)

        except Exception as e:
            logger.exception("ERROR_in_worker_loop")
            shutdown_event.wait(poll_interval)