import sys
import inspect
import os

class ExecutionTracer:
    def __init__(self, target_directory: str):
        self.target_directory = os.path.abspath(target_directory)
        self.trace_log = []
        self.call_depth = 0

    def start(self):
        self.trace_log = []
        self.call_depth = 0
        
        try:
            sys.monitoring.use_tool_id(sys.monitoring.DEBUGGER_ID, "pytest-semantic")
        except ValueError:
            # Might already be in use from a previous test
            try:
                sys.monitoring.free_tool_id(sys.monitoring.DEBUGGER_ID)
                sys.monitoring.use_tool_id(sys.monitoring.DEBUGGER_ID, "pytest-semantic")
            except ValueError:
                pass
            
        events = (
            sys.monitoring.events.PY_START |
            sys.monitoring.events.PY_RETURN |
            sys.monitoring.events.RAISE |
            sys.monitoring.events.PY_UNWIND
        )
        sys.monitoring.set_events(sys.monitoring.DEBUGGER_ID, events)
        
        sys.monitoring.register_callback(sys.monitoring.DEBUGGER_ID, sys.monitoring.events.PY_START, self._on_py_start)
        sys.monitoring.register_callback(sys.monitoring.DEBUGGER_ID, sys.monitoring.events.PY_RETURN, self._on_py_return)
        sys.monitoring.register_callback(sys.monitoring.DEBUGGER_ID, sys.monitoring.events.RAISE, self._on_raise)
        sys.monitoring.register_callback(sys.monitoring.DEBUGGER_ID, sys.monitoring.events.PY_UNWIND, self._on_unwind)

    def stop(self):
        try:
            sys.monitoring.set_events(sys.monitoring.DEBUGGER_ID, 0)
            sys.monitoring.free_tool_id(sys.monitoring.DEBUGGER_ID)
        except ValueError:
            pass

    def get_log_string(self) -> str:
        return "\n".join(self.trace_log)

    def _should_trace_file(self, filepath: str) -> bool:
        if not filepath or filepath.startswith('<'):
            return False
            
        abs_path = os.path.abspath(filepath)
        
        # Prevent self-tracing
        if abs_path == os.path.abspath(__file__):
            return False
        
        # Must be in the project dir
        if not abs_path.startswith(self.target_directory):
            return False
            
        # Ignore python environment packages 
        if "site-packages" in abs_path or ".venv" in abs_path:
            return False
            
        return True

    def _format_args(self, frame) -> str:
        # Extract the local variables from the frame at the moment of the function call
        arg_info = inspect.getargvalues(frame)
        args_dict = {}
        
        sensitive_keys = {"password", "secret", "token", "api_key", "auth", "credential", "cert"}
        
        def _sanitize_val(k: str, v):
            k_lower = k.lower()
            if any(sensitive in k_lower for sensitive in sensitive_keys):
                return "[REDACTED]"
            return v

        for arg in arg_info.args:
            val = arg_info.locals.get(arg)
            args_dict[arg] = _sanitize_val(arg, val)
            
        if arg_info.varargs and arg_info.varargs in arg_info.locals:
            val = arg_info.locals[arg_info.varargs]
            args_dict[f"*{arg_info.varargs}"] = _sanitize_val(arg_info.varargs, val)
            
        if arg_info.keywords and arg_info.keywords in arg_info.locals:
            val = arg_info.locals[arg_info.keywords]
            args_dict[f"**{arg_info.keywords}"] = _sanitize_val(arg_info.keywords, val)
            
        final_str = str(args_dict)
        if len(final_str) > 500:
            final_str = final_str[:500] + "... [truncated]"
        return final_str

    def _on_py_start(self, code, instruction_offset, *args):
        filepath = code.co_filename
        if not self._should_trace_file(filepath):
            return sys.monitoring.DISABLE
            
        func_name = code.co_name
        indent = "  " * self.call_depth
        
        try:
            frame = sys._getframe(1)
            args_str = self._format_args(frame)
        except Exception:
            args_str = "{}"
            
        log_entry = f"{len(self.trace_log) + 1}. {indent}[CALLED] {func_name}({args_str})"
        self.trace_log.append(log_entry)
        
        # Fetch source code for deep LLM context
        try:
            source_lines, _ = inspect.getsourcelines(code)
            source_code = "".join(source_lines)
            self.trace_log.append(f"{indent}# Source code of {func_name}:\n{indent}{source_code.strip()}\n")
        except OSError:
            pass
            
        self.call_depth += 1

    def _on_py_return(self, code, instruction_offset, retval, *args):
        filepath = code.co_filename
        if not self._should_trace_file(filepath):
            return sys.monitoring.DISABLE
            
        self.call_depth = max(0, self.call_depth - 1)
        indent = "  " * self.call_depth
        func_name = code.co_name
        
        return_val_str = str(retval)
        if len(return_val_str) > 500:
            return_val_str = return_val_str[:500] + "... [truncated]"
            
        log_entry = f"{len(self.trace_log) + 1}. {indent}[RETURNED] {func_name} -> {return_val_str}"
        self.trace_log.append(log_entry)

    def _on_raise(self, code, instruction_offset, exception, *args):
        filepath = code.co_filename
        if not self._should_trace_file(filepath):
            return None
            
        indent = "  " * self.call_depth
        func_name = code.co_name
        
        exc_str = f"{type(exception).__name__}: {str(exception)}"
        log_entry = f"{len(self.trace_log) + 1}. {indent}[RAISED] {func_name} -> {exc_str}"
        self.trace_log.append(log_entry)

    def _on_unwind(self, code, instruction_offset, exception, *args):
        filepath = code.co_filename
        if not self._should_trace_file(filepath):
            return None
            
        self.call_depth = max(0, self.call_depth - 1)
        indent = "  " * self.call_depth
        func_name = code.co_name
        
        # sys.settrace historically triggered a 'return' event with None when unwinding from an exception.
        # We must replicate this to maintain cache hashes.
        log_entry = f"{len(self.trace_log) + 1}. {indent}[RETURNED] {func_name} -> None"
        self.trace_log.append(log_entry)
