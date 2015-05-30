import logging
from ..baselex import EPS, EOF
from ..common import Token
from .common import ParserException, ParserGenerationException


class Action:
    def __repr__(self):
        return 'Action'

    def __eq__(self, other):
        return str(self) == str(other)


class Shift(Action):
    def __init__(self, to_state):
        self.to_state = to_state

    def __repr__(self):
        return 'Shift({})'.format(self.to_state)


class Reduce(Action):
    def __init__(self, rule):
        self.rule = rule

    def __repr__(self):
        return 'Reduce({})'.format(self.rule)


class Accept(Reduce):
    def __repr__(self):
        return 'Accept({})'.format(self.rule)


class Item:
    """
        Represents a partially parsed item
        It has a production it is looking for, a position
        in this production called the 'dot' and a look ahead
        symbol that must follow this item.
    """
    def __init__(self, production, dotpos, look_ahead):
        self.production = production
        self.dotpos = dotpos
        assert self.dotpos <= len(self.production.symbols)
        self.look_ahead = look_ahead
        self._is_shift = self.dotpos < len(self.production.symbols)
        self.IsShift = self._is_shift
        if self.IsShift:
            self.Next = self.production.symbols[self.dotpos]
        self._data = (self.production, self.dotpos, self.look_ahead)
        self._hash = self._data.__hash__()

    def __eq__(self, other):
        if type(other) is type(self):
            return self._data == other._data
        return False

    def __hash__(self):
        return self._hash

    @property
    def is_reduce(self):
        """ Check if this item has the dot at the end """
        return not self._is_shift

    def can_shift_over(self, symbol):
        """ Determines if this item can shift over the given symbol """
        return self._is_shift and self.Next == symbol

    def shifted(self):
        """ Creates a new item that is shifted one position """
        return Item(self.production, self.dotpos + 1, self.look_ahead)

    @property
    def NextNext(self):
        """ Gets the symbol after the next symbol, or EPS if at the end """
        if self.dotpos + 1 >= len(self.production.symbols):
            return EPS
        else:
            return self.production.symbols[self.dotpos + 1]

    def __repr__(self):
        prod = self.production
        predot = ' '.join(prod.symbols[0:self.dotpos])
        postdot = ' '.join(prod.symbols[self.dotpos:])
        name = prod.name
        args = (name, predot, postdot, self.look_ahead)
        return '[{} -> {} . {} -> {}]'.format(*args)


class LRParser:
    """ LR parser automata. This class takes goto and action table
        and can then process a sequence of tokens.
    """
    def __init__(self, action_table, goto_table, start_symbol):
        self.action_table = action_table
        self.goto_table = goto_table
        self.start_symbol = start_symbol

    def parse(self, lexer):
        """ Parse an iterable with tokens """
        assert hasattr(lexer, 'next_token')
        stack = [0]
        r_data_stack = []
        look_ahead = lexer.next_token()
        assert type(look_ahead) is Token
        # TODO: exit on this condition:
        while stack != [0, self.start_symbol, 0]:
            state = stack[-1]   # top of stack
            key = (state, look_ahead.typ)
            if key not in self.action_table:
                raise ParserException(
                    'Error parsing at character {0}'.format(look_ahead))
            action = self.action_table[key]
            if type(action) is Reduce:
                f_args = []
                prod = self.grammar.productions[action.rule]
                for s in prod.symbols:
                    stack.pop()
                    stack.pop()
                    f_args.append(r_data_stack.pop())
                f_args.reverse()
                r_data = None
                if prod.f:
                    r_data = prod.f(*f_args)
                state = stack[-1]
                stack.append(prod.name)
                stack.append(self.goto_table[(state, prod.name)])
                r_data_stack.append(r_data)
            elif type(action) is Shift:
                stack.append(look_ahead.typ)
                stack.append(action.to_state)
                r_data_stack.append(look_ahead)
                look_ahead = lexer.next_token()
                assert type(look_ahead) is Token
            elif type(action) is Accept:
                # Pop last rule data off the stack:
                f_args = []
                param = self.grammar.productions[action.rule]
                for s in param.symbols:
                    stack.pop()
                    stack.pop()
                    f_args.append(r_data_stack.pop())
                f_args.reverse()
                if param.f:
                    ret_val = param.f(*f_args)
                else:
                    ret_val = None
                # Break out!
                stack.append(param.name)
                stack.append(0)
                break
        # At exit, the stack must be 1 long
        # TODO: fix that this holds:
        # assert stack == [0, self.start_symbol, 0]
        return ret_val


def calculate_first_sets(grammar):
    """
        Calculate first sets for each grammar symbol
        This is a dictionary which maps each grammar symbol
        to a set of terminals that can be encountered first
        when looking for the symbol.
    """
    first = {}
    nullable = {}
    for terminal in grammar.terminals | {EOF, EPS}:
        first[terminal] = set([terminal])
        nullable[terminal] = False
    for nt in grammar.nonterminals:
        first[nt] = set()
        nullable[nt] = False
    while True:
        some_change = False
        for rule in grammar.productions:
            # Check for null-ability:
            if all(nullable[beta] for beta in rule.symbols):
                if not nullable[rule.name]:
                    nullable[rule.name] = True
                    some_change = True
            # Update first sets:
            for beta in rule.symbols:
                if not nullable[beta]:
                    if first[beta] - first[rule.name]:
                        first[rule.name] |= first[beta]
                        some_change = True
                    break
        if not some_change:
            break
    return first


class LrParserBuilder:
    """ Construct goto and action tables according to LALR algorithm """
    def __init__(self, grammar):
        self.grammar = grammar
        self._first = None  # Cached first set

    @property
    def first(self):
        """
          The first set is a mapping from a grammar symbol to a set of
          set of all terminal symbols that can be the first terminal when
          looking for the grammar symbol
        """
        if not self._first:
            self._first = calculate_first_sets(self.grammar)
        return self._first

    def closure(self, itemset):
        """ Expand itemset by using epsilon moves """
        worklist = list(itemset)

        def addIt(itm):
            if itm not in itemset:
                itemset.add(itm)
                worklist.append(itm)

        def first2(itm):
            # When using the first sets, create a copy:
            f = set(self.first[itm.NextNext])
            if EPS in f:
                f.discard(EPS)
                f.add(itm.look_ahead)
            return f
        # Start of algorithm:
        while worklist:
            item = worklist.pop(0)
            if not item.IsShift:
                continue
            if not (item.Next in self.grammar.nonterminals):
                continue
            C = item.Next
            for add_p in self.grammar.productions_for_name(C):
                for b in first2(item):
                    addIt(Item(add_p, 0, b))
        return frozenset(itemset)

    def initial_item_set(self):
        """ Calculates the initial item set """
        iis = set()
        for p in self.grammar.productions_for_name(self.grammar.start_symbol):
            iis.add(Item(p, 0, EOF))
        return self.closure(iis)

    def next_item_set(self, itemset, symbol):
        """
            Determines the next itemset for the current set and a symbol
            This is the goto procedure
        """
        next_set = set()
        for item in itemset:
            if item.can_shift_over(symbol):
                next_set.add(item.shifted())
        return self.closure(next_set)

    def generate_parser(self):
        """ Generates a parser from the grammar """
        logger = logging.getLogger('yacc')
        logger.debug('Generating parser from {}'.format(self))
        action_table, goto_table = self.generate_tables()
        p = LRParser(action_table, goto_table, self.grammar.start_symbol)
        p.grammar = self.grammar
        logger.debug('Parser generated')
        logger.debug('Goto table: {}'.format(len(goto_table)))
        logger.debug('Action table: {}'.format(len(action_table)))
        return p

    def gen_canonical_set(self, iis):
        states = set()
        worklist = []
        transitions = {}
        indici = {}

        def addSt(s):
            if s not in states:
                worklist.append(s)
                indici[s] = len(indici)
                states.add(s)
        addSt(iis)
        while len(worklist) > 0:
            itemset = worklist.pop(0)
            for symbol in self.grammar.Symbols:
                nis = self.next_item_set(itemset, symbol)
                if not nis:
                    continue
                addSt(nis)
                transitions[(indici[itemset], symbol)] = indici[nis]
        return states, transitions, indici

    def generate_tables(self):
        """ Generate parsing tables """
        # If no start symbol set, pick the first one!
        if not self.grammar.start_symbol:
            self.grammar.start_symbol = self.grammar.productions[0].name

        self.grammar.check_symbols()
        action_table = {}
        goto_table = {}
        iis = self.initial_item_set()

        # First generate all item sets by using the nextItemset function:
        states, transitions, indici = self.gen_canonical_set(iis)

        def setAction(state, t, action):
            assert isinstance(action, Action)
            key = (state, t)
            assert type(state) is int
            assert type(t) is str
            if key in action_table:
                action2 = action_table[key]
                if action != action2:
                    if (type(action2) is Reduce) and (type(action) is Shift):
                        # Automatically resolve and do the shift action!
                        # Simple, but almost always what you want!!
                        action_table[key] = action
                    elif isinstance(action2, Shift) and \
                            isinstance(action, Reduce):
                        pass
                    else:
                        a1 = str(action)
                        a2 = str(action2)
                        prod = self.grammar.productions[action.rule]
                        prod2 = self.grammar.productions[action2.rule]
                        raise ParserGenerationException('LR construction conflict {} vs {} ({} vs {})'.format(a1, a2, prod, prod2))
            else:
                action_table[key] = action

        # Fill action table:
        for state in states:
            state_nr = indici[state]
            # Detect conflicts:
            for item in state:
                if item.IsShift and item.Next in self.grammar.terminals:
                    # Rule 1, a shift item:
                    nextstate = transitions[(state_nr, item.Next)]
                    setAction(state_nr, item.Next, Shift(nextstate))
                if item.is_reduce:
                    if item.production.name == self.grammar.start_symbol and item.look_ahead == EOF:
                        # Rule 3: accept:
                        act = Accept(self.grammar.productions.index(item.production))
                    else:
                        # Rule 2, reduce item:
                        act = Reduce(self.grammar.productions.index(item.production))
                    setAction(state_nr, item.look_ahead, act)
            for nt in self.grammar.nonterminals:
                key = (state_nr, nt)
                if key in transitions:
                    goto_table[key] = transitions[key]
        return action_table, goto_table
