"""
This module implements the Thread class.
"""


class Thread:
    """
    This class represents a Thread.
    """

    def __init__(self, id, function, *args):
        self.id = id
        self.function = function
        self.args = args
