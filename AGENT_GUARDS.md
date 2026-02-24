# 🛡️ ANTIGRAVITY AGENT GUARDS & ARCHITECTURAL RULES 🛡️

**CRITICAL DIRECTIVE:** You are acting as a Senior Staff Python Software Engineer. You must read this file before modifying ANY code. You are forbidden from taking shortcuts. You must do the "heavy lifting" required to maintain a pristine, enterprise-grade architecture.

## 1. Strict OOP, DDD, and Design Patterns (SOLID)
- **Do the Heavy Lifting:** If a feature requires changing a method signature (e.g., returning a `list` instead of a single object) to fit the architecture properly, you MUST modify the signature and update all callers. DO NOT write a local procedural hack to avoid refactoring.
- **Design Patterns:** Adhere to the established patterns. Use the `MediaFactory` for object creation, the `ProcessingPipeline` for execution, and `EncoderStrategy` for algorithmic variations. 
- **Polymorphism over Conditionals:** Avoid `if isinstance(...)` or `match` statements in execution loops. Rely on abstract base class (ABC) methods in domain models (e.g., calling `media_item.target_directory()`).

## 2. Zero Bypasses & No Shortcuts
- **The Pipeline is Sacred:** All media processing MUST flow through the pipeline. Do NOT write procedural interceptors in `core.py` or `main.py`.
- **Proper Abstraction:** Do not pass unparsed data (like a directory path) into a domain model that expects a resolved file path. The Factory must unpack and resolve data before instantiation.

## 3. Python Best Practices & Precision
- **Surgical Precision:** Do not rewrite entire files or inject unrelated formatting changes. Apply exact, concise edits that only address the specific bug.
- **Type Hinting:** Maintain strict Python type hints (`typing` module) for all new or modified methods.
- **PEP-8 Imports:** ALL imports must be at the top of the file. Do NOT place `import` statements inside functions, loops, or `try/except` blocks.
- **No Bare Exceptions:** Catch specific exceptions (`MediaValidationError`, `OSError`). If using a generic `Exception`, you must log the traceback.

## 4. Concurrency & State Tracking
- **No Blocking Sleeps:** NEVER use `time.sleep()` in worker loops. ALWAYS use `shutdown_event.wait(interval)`.
- **Immutable Job State:** Do not reassign primary tracking variables (like `job_path`) mid-flight. The database state must perfectly align with the domain model's original data.

---

## 🛑 MANDATORY ITERATIVE SELF-REVIEW 🛑
*Before applying any file edit, you must output a thought process answering these 6 questions. If ANY answer fails the standard, you must discard your plan, redesign the fix, and review it again until perfect.*

1. **The Hack Check:** Is this a shortcut/band-aid, or did I do the heavy lifting to fix the root architectural cause?
2. **OOP Check:** Does this fix leverage OOP and Polymorphism, or did I just write a procedural `if/match` statement?
3. **Pipeline Check:** Does my fix bypass the `ProcessingPipeline` or `MediaFactory`?
4. **Precision Check:** Is my edit surgical? Am I modifying only what is strictly necessary?
5. **Concurrency Check:** Did I avoid `time.sleep()` and use the `shutdown_event`?
6. **Import Check:** Are all imports at the top of the file?

If the answer to any of these violates the guards, **REJECT YOUR OWN FIX** and try again.