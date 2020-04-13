brick_mappings = {}

def register_handler(*names):
    def dec(f):
        for name in names:
            brick_mappings[name] = f
        return f
    return dec