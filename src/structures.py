class Stack:
    def __init__(self):
        self.stack = []

    def is_empty(self):
        return not len(self.stack)

    def push(self, element):
        self.stack.append(element)
        return self.stack

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return "Stack is empty"

    def top(self):
        if not self.is_empty():
            return self.stack[-1]
        return "Stack is empty"