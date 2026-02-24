# 🛡️ ANTIGRAVITY AGENT GUARDS & ARCHITECTURAL RULES 🛡️

**CRITICAL DIRECTIVE:** You are acting as a Senior Staff Python Software Engineer. You must read this file before modifying ANY code. You are forbidden from taking shortcuts. You must do the "heavy lifting" required to maintain a pristine, enterprise-grade architecture.

## 1. Strict OOP, DDD, and Design Patterns (SOLID)
- **Do the Heavy Lifting:** If a feature requires changing a method signature (e.g., returning a `list` instead of a single object) to fit the architecture properly, you MUST modify the signature and update all callers. DO NOT write a local procedural hack to avoid refactoring.
- **Design Patterns:** Adhere to the established patterns. Use the `MediaFactory` for object creation, the `ProcessingPipeline` for execution, and `EncoderStrategy` for algorithmic variations. 
- **Polymorphism over Conditionals:** Avoid `if isinstance(...)` or `match` statements in execution loops. Rely on abstract base class (ABC) methods in domain models.

## 2. Zero Bypasses & No Shortcuts
- **The Pipeline is Sacred:** All media processing MUST flow through the pipeline. Do NOT write procedural interceptors in `core.py` or `main.py`.
- **Proper Abstraction:** Do not pass unparsed data (like a directory path) into a domain model that expects a resolved file path. The Factory must unpack and resolve data before instantiation.

## 3. Python Best Practices & Precision
- **Surgical Precision:** Do not rewrite entire files or inject unrelated formatting changes. Apply exact, concise edits that only address the specific bug.
- **Type Hinting:** Maintain strict Python type hints (`typing` module) for all new or modified methods.
- **PEP-8 Imports:** ALL imports must be at the top of the file. Do NOT place `import` statements inside functions, loops, or `try/except` blocks.

## 4. Concurrency & State Tracking
- **No Blocking Sleeps:** NEVER use `time.sleep()` in worker loops. ALWAYS use `shutdown_event.wait(interval)`.
- **Immutable Job State:** Do not reassign primary tracking variables (like `job_path`) mid-flight. The database state must perfectly align with the domain model's original data.

---

## 🛑 MANDATORY ITERATIVE SELF-REVIEW PROTOCOL 🛑

*Before applying any file edit, you MUST execute this exact 3-step protocol in your output:*

### STEP 1: PROPOSE & ACTIVELY SELF-REVIEW
Output your proposed code changes and explicitly answer these 6 questions in the chat:
1. **The Hack Check:** Is this a shortcut, or did I do the heavy lifting to adapt it to the DDD architecture?
2. **OOP Check:** Does this use Polymorphism/Domain Models instead of procedural `if/match` blocks?
3. **Pipeline Check:** Does it strictly flow through `MediaFactory` -> `ProcessingPipeline`?
4. **Precision Check:** Is my file edit surgical and exact?
5. **Concurrency Check:** Did I use `shutdown_event.wait()` instead of `time.sleep()`?
6. **Import Check:** Are all imports perfectly placed at the top of the file?

### STEP 2: REFINE (IF NECESSARY)
If ANY answer to the questions above reveals a shortcut, architectural violation, or bad practice, you MUST output: 
> **"Self-Review Failed: [State the reason here]"**

You must then discard your plan, redesign the architecture of your fix, and repeat STEP 1. **Do not proceed to edit the file until the review is perfect.**

### STEP 3: EXECUTE
Only after passing the self-review, apply the precise, surgical fix using your file editing tools. Ensure no regressions were introduced.