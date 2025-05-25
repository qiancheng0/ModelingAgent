import os
import json

class SharedContext:
    def __init__(self, config):
        self.config = config
        self.context = {}
        log_dir = config["log_dir"]

        self.log_file = os.path.join(log_dir, "log")
        self.log_json = os.path.join(log_dir, "context.json")
        
        # Initialize the log file
        os.makedirs(log_dir, exist_ok=True)
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("Log file created, initializing ...\n")
            f.write(json.dumps(config, indent=4, ensure_ascii=False))
            f.write("\n\n\n")
        
    
    def load_context(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.context = json.load(f)
    
    
    def save_context(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.context, f, indent=4, ensure_ascii=False)
    
        
    def add_context(self, key, value):
        self.context[key] = value
        # add context along with checkpointing
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"Added context - {key}:\n")
            try:
                f.write(json.dumps(value, indent=4, ensure_ascii=False))
            except:
                f.write(str(value))
            f.write("\n\n\n")
        
        self.save_context(self.log_json)
    
    
    def get_context(self, key):
        if key not in self.context:
            raise Exception("Key not found in context")
        return self.context[key]


    def delete_context(self, key):
        if key in self.context:
            del self.context[key]
            
    def from_dict(self, ctx: dict):
        """Load context from a Python dict (compat for old code)."""
        self.context = ctx or {}
        self.save_context(self.log_json)
