class table:
    # This init runs when you write @TableNameDecorator(name='...')
    def __init__(self, name=''):
        # Store the configuration argument
        self.name = name

    # This __call__ runs when the decorator actually wraps the target class
    def __call__(self, cls):
        # Modify the target class
        cls._table_name = self.name
        # Return the modified class
        return cls