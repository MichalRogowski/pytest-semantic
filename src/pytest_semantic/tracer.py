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
        sys.settrace(self._trace_calls)

    def stop(self):
        sys.settrace(None)

    def get_log_string(self) -> str:
        return "\n".join(self.trace_log)

    def _should_trace_file(self, filepath: str) -> bool:
        if not filepath or filepath.startswith('<'):
            return False
            
        abs_path = os.path.abspath(filepath)
        
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
        args_dict = {arg: arg_info.locals.get(arg) for arg in arg_info.args}
        
        if arg_info.varargs and arg_info.varargs in arg_info.locals:
            args_dict[f"*{arg_info.varargs}"] = arg_info.locals[arg_info.varargs]
            
        if arg_info.keywords and arg_info.keywords in arg_info.locals:
            args_dict[f"**{arg_info.keywords}"] = arg_info.locals[arg_info.keywords]
            
        return str(args_dict)

    def _trace_calls(self, frame, event, arg):
        if event == 'call':
            func_name = frame.f_code.co_name
            filepath = frame.f_code.co_filename
            
            if self._should_trace_file(filepath):
                indent = "  " * self.call_depth
                args_str = self._format_args(frame)
                
                log_entry = f"{len(self.trace_log) + 1}. {indent}[CALLED] {func_name}({args_str})"
                self.trace_log.append(log_entry)
                
                # Fetch source code for deep LLM context
                try:
                    # We might not be able to get source if it's dynamic
                    source_lines, _ = inspect.getsourcelines(frame.f_code)
                    source_code = "".join(source_lines)
                    self.trace_log.append(f"{indent}# Source code of {func_name}:\n{indent}{source_code.strip()}\n")
                except OSError:
                    pass
                
                self.call_depth += 1
                return self._trace_calls
            return None # Don't trace into this function's local lines if we didn't match the file rule
            
        elif event == 'return':
            func_name = frame.f_code.co_name
            filepath = frame.f_code.co_filename
            
            if self._should_trace_file(filepath):
                self.call_depth = max(0, self.call_depth - 1)
                indent = "  " * self.call_depth
                
                # 'arg' holds the return value for a 'return' event
                return_val_str = str(arg)
                # truncate massive return values?
                if len(return_val_str) > 500:
                    return_val_str = return_val_str[:500] + "... [truncated]"
                    
                log_entry = f"{len(self.trace_log) + 1}. {indent}[RETURNED] {func_name} -> {return_val_str}"
                self.trace_log.append(log_entry)
                
        elif event == 'exception':
            func_name = frame.f_code.co_name
            filepath = frame.f_code.co_filename
            
            if self._should_trace_file(filepath):
                indent = "  " * self.call_depth
                exc_type, exc_value, exc_traceback = arg
                
                exc_str = f"{exc_type.__name__}: {str(exc_value)}"
                log_entry = f"{len(self.trace_log) + 1}. {indent}[RAISED] {func_name} -> {exc_str}"
                self.trace_log.append(log_entry)
                
        return self._trace_calls
