from collections import namedtuple

RegisterClass = namedtuple(
    'RegisterClass', ['name', 'ir_types', 'typ', 'registers'])


class Register:
    """ Baseclass of all registers types """
    def __init__(self, name, num=None, aliases=()):
        assert isinstance(name, str)
        self.name = name
        self._num = num

        # If this register interferes with another register:
        self.aliases = aliases
        if num is not None:
            assert isinstance(num, int)

    def __repr__(self):
        return '{}'.format(self.name)

    @property
    def num(self):
        """ When the register is colored, this property can be used """
        assert self.is_colored
        return self._num

    @property
    def color(self):
        """ The coloring of this register """
        return self._num

    def set_color(self, color):
        self._num = color

    @property
    def is_colored(self):
        """ Determine whether the register is colored """
        return self.color is not None