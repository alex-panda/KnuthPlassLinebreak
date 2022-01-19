"""
Status: The algorithm works and an example of using the algorithm is finished,
    so I am done working on this module.

This is a module that implements the Knuth-Plass text formatting algorithm in
    Python. I wrote this one after Knuth-Plass.py because I thought the
    algorithm might be faster if it used linked list. Apparently, that is not
    the case as when I profiled this implementation the knuth_plass_breaks()
    method took twice as long as the origional in knuth_plass.py to do the same
    thing. I suspect that this is because of the extra baggage of having to
    jump from link to link instead of being able to get at each part of the
    list using an index outweighed the faster insert and remove times that the
    linked list provided.

Using the Knuth-Plass algorithm, one can beakup text into lines in such a way
    that each line has "minimum badness" as defined by the algorithm. It also
    figures out how large each space should be if you want to
    "FULL" A.K.A. "LEFT-RIGHT" justify the text.

There are 2 main parts to the algorithm:
    Part 1: Turning your text into a list of Glue, Box, and Penalty objects.
        This part is crucial as this is where you describe what your paragraph
        looks like as far as where you can break it up and how large the
        different components can be.

        A 'paragraph' (which is just a list of Glue, Box, and Penalty objects)
            is made up of 3 things.

            Glue:    The spaces that can chane width. Have a default width, but
                can shrink by `shrink` amount and stretch by `stretch` amount.

            Box:     An object of a static width such as a character like 'a',
                'A', 'b', '1', '2', etc. The algorithm only looks at the width,
                so could be a picture too, or something else (so long as the
                width describes the contents of the box). A word in a paragraph
                is typically described by a sequence of boxes, one for each
                letter of the word. No space will be put to break up the word
                unless you specify a Glue or Penalty within the word.

            Penalty: A place where you are specifically talking about whether
                to break the line or not. You can break in other places, such
                as between a Box and a Glue, but Penalties let you specify
                arbitrary points where you can break but incure a Penalty.
                Obviously, higher penalties are worse penalties. A penalty
                of INF (infinity) is a place where you cannot break
                and a penalty of -INF (negative infinity) is a place where you
                have to have a line break.

                The width of a penalty is the width of the typesetting material
                (the hyphen ('-') if breaking inside a word) that must be added
                if you break at this point. Typically, the width is 0.

    Part 2: The actual algorithm that looks at your list of Glue, Box, and
        Penalty objects and uses them to find the best way break up your
        paragraph such that the paragraph as a whole has the 'minimum badness',
        as described by the algorithm itself.

        After the paragraph is broken up into lines, then you can iterate over
        the Glue, Box, and Penalty objects that makes up each line and justify
        the resulting line left, middle, right, or full.
"""
from typing import List, Callable, Union, Dict, Generator, Tuple
from collections import namedtuple

class JUSTIFY:
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    FULL = "FULL"

WHITESPACE_CHARS = ' \t\r\n\f\v'
WHITESPACE = set(ch for ch in WHITESPACE_CHARS)
Num = Union[int, float]
INF = 10000
GLUE, BOX, PENALTY = "Glue", "Box", "Penalty"

# =============================================================================
# Specifications (Glue, Box, Penalty)
# -----------------------------------------------------------------------------

class Spec:
    def __init__(self):
        super().__init__()

    def is_glue(self):         return False
    def is_box(self):          return False
    def is_penalty(self):      return False
    def is_forced_break(self): return False

class Glue(Spec):
    """
    Glue refers to blank space that can vary its width in specified ways; it is
        an elastic mortar used between boxes in a typeset line.
    """
    __slots__ = ['width', 'stretch', 'shrink']
    t = GLUE
    def __init__(self, shrink:Num, width:Num, stretch:Num):
        """
        Init for a Glue Object. You can think of shrink, width, and stretch as
            shrink:  the max you can lessen the width by
            width:   ideal width
            stretch: the max amount of space you can add to the width

            In other words: this glue has minimum width (`width` - `shrink`) and
                maximum width (`width` + `stretch`)

        NOTE: in the paper, a Glue is specified with order
            "width, stretch, shrink". That makes absolutely no sense so I've
            changed the parameters to be in order "shrink, width, stretch"
            instead.
        """
        self.shrink: Num  = shrink
        self.width: Num   = width
        self.stretch: Num = stretch

    def r_width(self, r):
        """
        Returns the width of this glue for the given ratio r.
        """
        if r < 0: return self.width + (r * self.shrink)
        else:     return self.width + (r * self.stretch)

    def is_glue(self): return True

    def copy(self):
        return Glue(self.shrink, self.width, self.stretch)

    def __eq__(self, o:object):
        if isinstance(o, self.__class__):
            return o.width == self.width and o.stretch == self.stretch and o.shrink == self.shrink
        return False

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width}, stretch={self.stretch}, shrink={self.shrink})>'

class Box(Spec):
    """
    A box refers to something that is to be typeset: either a character from
        some font of type, or a black rectangle such as a horizontal or
        vertical rule, or something built up from several characters such as an
        accented letter or a mathematical formula. The contents of a box may be
        extremely complicated, or they may be extremely simple; the
        line-breaking algorithm does not peek inside a box to see what it
        contains, so we may consider the boxes to be sealed and locked.
    """
    __slots__ = ['width', 'value']
    t = BOX
    def __init__(self, width:Num, value:Num):
        self.width: Num = width # The fixed width of the box (so width of what is in the box)
        self.value: Num = value # Value is something like a glyph/character. Algorithm does not use this, only width param so value can be whatever you want, as long as the width reflects its width.

    def is_box(self): return True

    def copy(self):
        return Box(self.width, self.value)

    def __eq__(self, o:object):
        if isinstance(o, self.__class__):
            return o.width == self.width and o.value == self.value
        return False

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width}, value={self.value})>'

class Penalty(Spec):
    """
    Penalty specifications refer to potential places to end one line of a
        paragraph and begin another (AKA, a linebreak), with a certain
        ‘aesthetic cost’ indicating how desirable or undesirable such a
        breakpoint would be. The width of a penalty is how much typset material
        needs to be added if you break here AKA 0 if nothing and the width of
        a hyphen if you want to add a hyphen here because you are breaking off
        a word.
    """
    __slots__ = ['width', 'penalty', 'flagged']
    t = PENALTY
    def __init__(self, width:Num, penalty:Num, flagged:bool):
        self.width: Num   = width   # Width of extra typeset material (width of the hyphen)
        self.penalty: Num = penalty # The penalty to breaking here
        self.flagged: Num = flagged # Whether there is a hyphen here

    def is_penalty(self):      return True
    def is_forced_break(self): return (self.penalty == -INF)

    def copy(self):
        return Penalty(self.width, self.penalty, self.flagged)

    def __eq__(self, o:object):
        if isinstance(o, self.__class__):
            return o.width == self.width and o.penalty == self.penalty and o.flagged == self.flagged
        return False

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width}, penalty={self.penalty}, flagged={self.flagged})>'

Spec = Union[Glue, Box, Penalty]

# =============================================================================
# Parsing Text into List of Specs
# -----------------------------------------------------------------------------

def make_paragraph(text):
    """
    An example function that takes in text and returns a paragraph from it that
        can be used in the Knuth-Plass Algorithm.
    """
    # Turn chunk of text into a paragraph
    L = []
    for ch in text:
        if ch in ' \n':
            # Add the space between words
            #   it's 2 units +/- 1 so can be 1, 2, or 3 units long
            L.append(Glue(1, 2, 1))
        elif ch == '@':
            # Append forced break
            L.append(Penalty(0, -INF))

        elif ch == '~':
            # Append no-break so cannot break here under any circumstances
            L.append(Penalty(0, INF))

        else:
            # All characters are 1 unit wide
            L.append(Box(1, ch))

    # Append closing penalty and glue
    L.extend(std_paragraph_end())

    return L

def std_paragraph_end():
    """
    Returns the standard closing penalty for a paragraph as a list of Penalty,
        Glue, and Penalty Objects. Just extend your List[Spec] by it and it
        should end properly.
    """
    return [Penalty(0,  INF,   0), # Forced non-break (must not break here, otherwise a Box coming before the Glue after this would allow a break to be here)
            Glue(   0,    0, INF), # Glue that fills the rest of the last line (even if that fill is 0 width)
            Penalty(0, -INF,   1)] # Forced break (Ends last line)

# =============================================================================
# The Actual Knuth-Plass Algorithm
# -----------------------------------------------------------------------------

class Break:
    """
    A class representing a break in the text as calculated by the Knuth-Plass
    algorithm.
    """
    __slots__ = ["position", "line", "fitness_class", "total_width", "total_stretch", "total_shrink", "demerits", "previous", "previous_break", "next_break"]
    def __init__(self, position, line, fitness_class, total_width, total_stretch, total_shrink, demerits, previous=None, previous_break=None, next_break=None):
        self.position       = position
        self.line           = line
        self.fitness_class  = fitness_class
        self.total_width    = total_width
        self.total_stretch  = total_stretch
        self.total_shrink   = total_shrink
        self.demerits       = demerits
        self.previous       = previous # Used by algorithm

        # Used by linked list
        self.previous_break = previous_break
        self.next_break     = next_break

    def iterate_forward(self, start_with_self=True):
        """
        Since Breaks are in a linked list, this function lets you iterate
            forward in the list.

        The iteration starts at the next Break node forward.
        """
        curr = self if start_with_self else self.next_break

        while curr is not None:
            yield curr
            curr = curr.next_break

    def iterate_backward(self, start_with_self=True):
        """
        Since Breaks are in a linked list, this function lets you iterate
            backwards in the list.

        The iteration starts at the previous Break node backwards.
        """
        curr = self if start_with_self else self.previous_break

        while curr is not None:
            yield curr
            curr = curr.previous_break

    def iterate_front_to_back(self):
        """
        Garauntees that the iteration is happening from the first node to the
            last node (unless a link's previous_break or next_break has been
            messed up manually)
        """
        first_node = None
        for node in self.iterate_backward(True):
            first_node = node
        for node in first_node.iterate_forward(True):
            yield node

    def insert(self, break_obj):
        """
        Inserts a break object into this Break object's position in the linked list.
        """
        break_obj.remove_from_linked_list()

        # Connect previous break with break_obj
        if self.previous_break is not None:
            self.previous_break.next_break = break_obj
        break_obj.previous_break = self.previous_break

        # connect break_obj with self
        break_obj.next_break = self
        self.previous_break = break_obj

    def insert_after(self, break_obj):
        """
        Inserts the given Break object directly after this object.
        """
        if self.next_break is None:
            self.append(break_obj)
        else:
            self.next_break.insert(break_obj)

    def append(self, break_obj):
        # Remove from current list, if in one
        break_obj.remove_from_linked_list()

        # Find last node (could be this node)
        last_node = self
        for node in self.iterate_forward(False):
            last_node = node

        # Connect last node to the new one
        last_node.next_break = break_obj
        break_obj.previous_break = last_node

    def remove_from_linked_list(self):
        """
        Removes this Break from the linked list it is in.

        Returns the next_break in the list if possible or the previous_break if
            next_break is None
        """
        if self.previous_break is not None:
            self.previous_break.next_break = self.next_break

        if self.next_break is not None:
            self.next_break.previous_break = self.previous_break

        self.next_break = None
        self.previous_break = None

    def __len__(self):
        length = None
        for i, node in enumerate(self.iterate_front_to_back()):
            length = i

        return 0 if length is None else length + 1

    def copy(self):
        """
        Copies this Break object, not the linked list itself so not the previous_break
            and next_break.
        """
        return Break(self.position, self.line, self.fitness_class, self.total_width, self.total_stretch, self.total_shrink, self.demerits)

    def __repr__(self):
        return f"<{self.__class__.__name__}(pos={self.position}, line={self.line}, fitness_class={self.fitness_class}, total_width={self.total_width}, total_stretch={self.total_stretch}, total_shrink={self.total_shrink}, demerits={self.demerits})>"

    def list_str(self):
        """
        Returns the string representing the list that this Break is a part of.
        """
        out = '['

        first_node = None
        for node in self.iterate_backward(True):
            first_node = node

        out += repr(first_node)

        for node in first_node.iterate_forward(False):
            out += ', ' + repr(node)

        out += ']'
        return out

# -- Give the Algorithm Function Itself

BreakpointInfo = namedtuple('BreakpointInfo', ['break_point_obj', 'line_info'])
LineInfo = namedtuple('LineInfo', ["total_num_lines", "ratio", "line_num", "line_length", "line_contents"])

def knuth_plass_breaks(paragraph:List[Spec],
        line_lengths:Union[List[Num], Num, \
                Generator[Num, None, None]], # l1, l2,... in the paper
        looseness:int=0,                     # q in the paper
        tolerance:int=1,                     # rho in the paper
        fitness_demerit:Num=100,             # gamma in the paper
        flagged_demerit:Num=100,             # alpha in the paper
        ret_vals:bool=False
    ):
    """
    Takes in a list of Glue, Box, and Penalty objects, runs the Knuth-Plass
        algorithm, and yields the results.

    IMPORTANT : If you are trying to break up text, then it is very important
        that every single char in the text is represented by 1 box or glue
        because that is how the algorithm knows and returns what index of the
        text it is supposed to break it.

    paragraph : A list of Glue, Box, and Penalty items that you want the breaks
        for.
    line_lengths : a list of integers giving the lengths of each line.  The
        last element of the list is reused for subsequent lines after it.
    looseness : An integer value. If it's positive, the paragraph will be set
        to take that many lines more than the optimum value.   If it's negative,
        the paragraph is set as tightly as possible.  Defaults to zero, meaning the
        optimal length for the paragraph.
    tolerance : the maximum adjustment ratio allowed for a line.  Defaults to 1.
    fitness_demerit : additional value added to the demerit score when two
        consecutive lines are in different fitness classes.
    flagged_demerit : additional value added to the demerit score when breaking
        at the second of two flagged penalties.
    ret_vals : If True, it will return the values, otherwise this
        method returns the values as a generator. The generator implementation
        is default and saves on a lot of memmory, but means that the output can
        only iterated through once before you have to run this method again to
        get another generator.

    return : the return value is a generator/list that returns BreakpointInfo
        namedtuples. These have the following format:

            BreakpointInfo(
                break_point_obj: the actual breakpoint object generated

                line_info: namedtuple (contains info for each line) LineInfo(

                    total_num_lines: int, the total number of lines generated

                    ratio: int, for each Glue object on this line, give this
                    ratio to the Glue object's `r_width()` method to have the
                    method return what this Glue's width should be if you want
                    to JUSTIFY.FULL your text

                    line_num: int, the 1-indexed number of the line you are
                        currently on. So the first line yielded by the generator
                        is line 1

                    line_length: int, how long this line is supposed to be,
                        according to what was given to the generator

                    line_contents :
                        the list/generator that yields Glue, Box, and Penalty
                        objects that specify what is supposed to be on this line
                )
            )
    """
    def is_feasible_breakpoint(i):
        """Return true if position 'i' is a feasible breakpoint."""
        spec = paragraph[i]
        if spec.is_penalty() and spec.penalty < INF:
            # Forced Breakpoint
            return True
        elif i > 0 and paragraph[i-1].is_box() and spec.is_glue():
            # Breakpoint when glue directly follows a box
            return True
        else:
            return False

    if isinstance(line_lengths, int) or isinstance(line_lengths, float):
        line_lengths = [line_lengths]

    #m = len(paragraph)
    if len(paragraph) == 0: return [] # No text, so no breaks

    # Precompute the running sums of width, stretch, and shrink (W,Y,Z in the
    # original paper).  These make it easy to measure the width/stretch/shrink
    # between two indexes; just compute sum_*[pos2] - sum_*[pos1].  Note that
    # sum_*[i] is the total up to but not including the box at position i.
    sum_width = {}; sum_stretch = {}; sum_shrink = {}
    width_sum = stretch_sum = shrink_sum = 0
    for i, spec in enumerate(paragraph):
        sum_width[i] = width_sum
        sum_stretch[i] = stretch_sum
        sum_shrink[i] = shrink_sum

        width_sum += spec.width

        if spec.is_glue():
            stretch_sum = stretch_sum + spec.stretch
            shrink_sum  = shrink_sum  + spec.shrink

    def measure_width(pos1, pos2):
        """Add up the widths between positions 1 and 2"""
        return sum_width[pos2] - sum_width[pos1]

    def measure_stretch(pos1, pos2):
        """Add up the stretch between positions 1 and 2"""
        return sum_stretch[pos2] - sum_stretch[pos1]

    def measure_shrink(pos1, pos2):
        """Add up the shrink between positions 1 and 2"""
        return sum_shrink[pos2] - sum_shrink[pos1]

    def compute_adjustment_ratio(pos1, pos2, line, line_lengths):
        """Compute adjustment ratio for the line between pos1 and pos2"""
        ideal_width = measure_width(pos1, pos2) # ideal width

        if paragraph[pos2].is_penalty():
            ideal_width += paragraph[pos2].width

        # Get the length of the current line; if the line_lengths list
        # is too short, the last value is always used for subsequent
        # lines.
        if line < len(line_lengths):
            available_width = line_lengths[line]
        else:
            available_width = line_lengths[-1]

        # Compute how much the contents of the line would have to be
        # stretched or shrunk to fit into the available space.
        if ideal_width < available_width:
            # You would have to stretch this line if you want it to fit on the
            #   desired line
            y = measure_stretch(pos1, pos2) # The total amount of stretch (in whatever units all the parts of the paragraph are measured in) you can stretch this line by

            if y > 0:
                # Since it is possible to stretch the line, found out how much
                #   you should stretch it by to take up the full width of the line
                r = (available_width - ideal_width) / float(y)
            else:
                r = INF

        elif ideal_width > available_width:
            # Must shrink the line by removing space from glue if you want it
            #   to fit on the line
            z = measure_shrink(pos1, pos2) # Total amount you could possibly shrink this line by to make it fit on the current desired line

            if z > 0:
                # Since it is possible to shrink the line, find how much you
                #   should shrink it to fit it perfectly (width matches desired
                #   width) on the line
                r = (available_width - ideal_width) / float(z)
            else:
                r = INF
        else:
            # Exactly the right length!
            r = 0

        return r

    A = Break(position=0, line=0, fitness_class=1, total_width=0, total_stretch=0, total_shrink=0, demerits=0)
    first_active_node = A # The first node in the active_nodes linked list. This node will never change

    def add_active_node(first_active_node, node):
        """
        Add a node to the active node list.

        The node is added so that the list of active nodes is always
        sorted by line number, and so that the set of (position, line,
        fitness_class) tuples has no repeated values.
        """
        # Find the first index at which the active node's line number is equal
        # to or greater than the line for 'node'.  This gives us the insertion
        # point.
        for curr_node in first_active_node.iterate_forward(True):

            insertion_node = curr_node

            if curr_node.line >= node.line:
                break

        # Check if there's a node with the same line number and position and
        # fitness. This lets us ensure that the list of active nodes always has
        # unique (line, position, fitness) values.
        for curr_node in insertion_node.iterate_forward(True):
            if curr_node.line != node.line:
                break

            if (curr_node.fitness_class == node.fitness_class \
                 and curr_node.position == node.position):
                # A match, so just return without adding the node
                return

        # Insert the new node so that the line numbers are in order
        if insertion_node.line < node.line:
            insertion_node.insert_after(node)
        else:
            insertion_node.insert(node)

    # -- End Function

    max_len = 0
    breaks_to_remove = []
    for i, B in enumerate(paragraph):
        max_len = max(max_len, len(first_active_node))

        # Determine if this box is a feasible breakpoint and
        # perform the main loop if it is.
        if is_feasible_breakpoint(i):
            # Loop over the list of active nodes, and compute the fitness
            # of the line formed by breaking at A and B.  The resulting
            breaks = [] # List of feasible breaks
            for A in first_active_node.iterate_forward(True):
                r = compute_adjustment_ratio(A.position, i, A.line, line_lengths)

                # 1. You cannot shrink the line more than the shrinkage
                #   available (but, notice that you can stretch the line more
                #   than specified)
                # 2. If B, the new breakpoint we are currently looking it, is a
                #   forced breakpoint, then you have to take it instead of any
                #   previous breakpoint so remove the breakpoints that do not
                #   allow you to take this current breakpoint B
                if (r < -1 or B.is_forced_break()):
                    # Deactivate node A so long as it will not empty all active nodes
                    breaks_to_remove.append(A)

                if -1 <= r <= tolerance:
                    # Compute demerits and fitness class
                    p = B.penalty if B.is_penalty() else 0
                    if p >= 0:
                        demerits = (1 + 100 * abs(r)**3 + p) ** 3
                    elif B.is_forced_break():
                        demerits = (1 + 100 * abs(r)**3) ** 2 - p**2
                    else:
                        demerits = (1 + 100 * abs(r)**3) ** 2

                    curr_f = 1 if spec.is_penalty() and spec.flagged else 0

                    next_spec = paragraph[A.position]
                    next_f = 1 if next_spec.is_penalty() and next_spec.flagged else 0
                    demerits += (flagged_demerit * curr_f * next_f)

                    # Figure out the fitness class of this line (tight, loose,
                    # very tight, or very loose).
                    if   r < -.5: fitness_class = 0
                    elif r <= .5: fitness_class = 1
                    elif r <= 1:  fitness_class = 2
                    else:         fitness_class = 3

                    # If two consecutive lines are in very different fitness
                    # classes, add to the demerit score for this break.
                    if abs(fitness_class - A.fitness_class) > 1:
                        demerits = demerits + fitness_demerit

                    # Record a feasible break from A to B
                    brk = Break(
                            position      = i,
                            line          = A.line + 1,
                            fitness_class = fitness_class,
                            total_width   = sum_width[i],
                            total_stretch = sum_stretch[i],
                            total_shrink  = sum_shrink[i],
                            demerits      = demerits,
                            previous      = A
                        )
                    breaks.append(brk)

            # end for A in active_nodes

            # Now remove all nodes that need to be removed from the
            # active_nodes list
            while breaks_to_remove:
                brk = breaks_to_remove.pop()

                if brk is first_active_node:
                    # Since brk is the first node in the linked list and we
                    # want to remove brk, we have to either update
                    # first_active_node before deleting it or just
                    # not delete it if it is the only node in the list
                    if first_active_node.next_break is not None:
                        first_active_node = first_active_node.next_break
                        brk.remove_from_linked_list()
                else:
                    brk.remove_from_linked_list()

            # Add in the new breaks
            if breaks:
                for brk in breaks:
                    add_active_node(first_active_node, brk)

        # end if self.feasible_breakpoint()
    # end for i in range(m)

    # Find the active node with the lowest number of demerits.
    # NOTE: this loop MUST use "<", not "<=" because "<=" leads to the lines
    #   with maximum allowable stretch to be used i.e. the most space possible
    #   will be added to each line
    A = first_active_node
    for node in first_active_node.iterate_forward(False):
        if node.demerits < A.demerits:
            A = node

    if looseness != 0:
        # The search for the appropriate active node is a bit more complicated;
        # we look for a node with a paragraph length that's as close as
        # possible to (A.line + looseness) with the minimum number of demerits.

        best = 0
        d = INF
        for br in first_active_node.iterate_forward(True):
            delta = br.line - A.line

            # The two branches of this 'if' statement are for handling values
            # of looseness that are either positive or negative.
            if ((looseness <= delta < best) or (best < delta < looseness)):
                s = delta
                d = br.demerits
                b = br

            elif delta == best and br.demerits < d:
                # This break is of the same length, but has fewer demerits and
                # hence is the one we should use.
                d = br.demerits
                b = br

        A = b

    # Generate the list of chosen break points
    breaks = []
    break_objs = []
    while A is not None:
        breaks.append(A.position)
        break_objs.append(A)
        A = A.previous
    break_objs.reverse()
    breaks.reverse()

    # -- Now Actually Yield/Return the Results

    assert breaks[0] == 0

    def line_length_gen():
        i = 0
        while True:
            if i < len(line_lengths):
                yield line_lengths[i]
            else:
                yield line_lengths[-1]
            i += 1

    total_num_lines = (len(breaks) - 1) # How many lines the text was broken into

    def ret_vals_gen():
        line_start = 0
        line_num = 0

        for break_point, line_length in zip(breaks[1:], line_length_gen()):
            ratio = compute_adjustment_ratio(line_start, break_point, line_num, line_lengths)

            def line_contents():
                for i in range(line_start, break_point, 1):
                    yield paragraph[i]

            # line_num + 1 because line_num is 0 indexed but line_num given should not be
            yield BreakpointInfo(break_point, LineInfo(total_num_lines, ratio, line_num + 1, line_length, line_contents()))

            line_num += 1
            line_start = break_point + 1

    if ret_vals:
        # Return the values as lists rather than a generator
        rets = []
        for break_point, line_info in ret_vals_gen():
            rets.append(BreakpointInfo(break_point, LineInfo(*line_info[:-1], tuple(spec.copy() for spec in line_info.line_contents))))
        return rets

    else:
        # Return a generator that will yield the values without taking up more memory
        return ret_vals_gen()

def str_for_breaks(breaks, justify:str=JUSTIFY.LEFT, end_mark:str=''):
    """
    Takes what is returned by the knuth_plass_breaks() function and turns it
        into a string depending on the given justification.

    Note: This method assumes that all boxes in the given breaks have
        characters (strings) in them and not other things like a picture or
        something.
    """
    def insert_spaces(string, num_spaces):
        """
        Inserts the given number of spaces into the given string, trying to put
            them inbetween words from the left side to the right.
        """
        while True:

            out = ''
            added_space = False
            add_space = False
            for ch in string:
                if num_spaces > 0 and add_space == True and ch in WHITESPACE:
                    out += ' '
                    num_spaces -= 1
                    added_space = True
                    add_space = False
                else:
                    add_space = True

                out += ch

            # If had no opportunity to add a space, then probably last line of
            # Justified paragraph so its left justified anyway. Just add a
            # space to the end.
            if not added_space and num_spaces > 0:
                out += ' '
                num_spaces -= 1

            if num_spaces <= 0:
                break

            string = out
            out = ''

        return out

    justify = justify.upper() # Justify constants are all upper-case, so make sure this matches as long as same word used
    out = ''
    curr_line = ''
    for break_point_obj, line_info  in breaks:

        total_num_lines = line_info.total_num_lines
        line_num        = line_info.line_num
        ratio           = line_info.ratio
        line_length     = line_info.line_length
        line_contents   = line_info.line_contents

        last_spec = None

        # -- Build the current line
        for spec in line_contents:
            if spec.is_glue():
                if justify == JUSTIFY.FULL and (not (line_num == total_num_lines)):
                    # Need to add space inbetween words to fully justify text
                    #   on the left and right
                    width = int(spec.r_width(ratio))
                else:
                    # Not Full justified, so no extra spaces between the words.
                    width = 1

                curr_line += ' ' * width

            elif spec.is_box():
                curr_line += spec.value # This assumes that the value is a string character

        # -- Justify The Built Line

        if (justify == JUSTIFY.LEFT) or (justify == JUSTIFY.FULL and line_num == total_num_lines):
            curr_line = curr_line.lstrip(WHITESPACE_CHARS)
            out += curr_line + (' ' * (line_length - len(curr_line)))

        elif justify == JUSTIFY.RIGHT:
            curr_line = curr_line.rstrip(WHITESPACE_CHARS)
            out += (' ' * (line_length - len(curr_line))) + curr_line

        elif justify == JUSTIFY.CENTER:
            curr_line = curr_line.strip(WHITESPACE_CHARS)

            total_spaces_needed = line_length - len(curr_line)

            # NOTE: this will skew the text of this line left by 1 space if
            # this line's text is not perfectly centerable. If had floating
            # point width spaces, then would be perfectly centered always, but
            # can't because using str's instead
            right_spaces  = total_spaces_needed // 2
            left_spaces = total_spaces_needed - right_spaces

            out += (' ' * left_spaces) + curr_line + (' ' * right_spaces)

        elif justify == JUSTIFY.FULL:
            # NOTE: Because the algorithm assumes that glues can have decimal
            # widths but strings need ints, we have cut off some space when we
            # converted them to integer widths. That is why we have to use
            # `insert_spaces` here: some space was probably cut off so we need
            # to add some back.
            curr_line = insert_spaces(curr_line, line_length - len(curr_line))
            out += curr_line
        else:
            raise Exception(f"Gave unknown justification specification: {justify}")

        #print(curr_line)
        curr_line = ''
        out += end_mark + "\n"
    return out

# =============================================================================
# Main
# -----------------------------------------------------------------------------

def main():
    short_text = """Among other public buildings in a certain town, which for many reasons it will be prudent to refrain from mentioning, and to which I will assign no fictitious name, there is one anciently common to most towns, great or small: to wit, a workhouse; and in this workhouse was born; on a day and date which I need not trouble myself to repeat, inasmuch as it can be of no possible consequence to the reader, in this stage of the business at all events; the item of mortality whose name is prefixed to the head of this chapter."""
    medium_text = """For the next eight or ten months, Oliver was the victim of a systematic course of treachery and deception. He was brought up by hand. The hungry and destitute situation of the infant orphan was duly reported by the workhouse authorities to the parish authorities. The parish authorities inquired with dignity of the workhouse authorities, whether there was no female then domiciled in “the house” who was in a situation to impart to Oliver Twist, the consolation and nourishment of which he stood in need. The workhouse authorities replied with humility, that there was not. Upon this, the parish authorities magnanimously and humanely resolved, that Oliver should be “farmed,” or, in other words, that he should be dispatched to a branch-workhouse some three miles off, where twenty or thirty other juvenile offenders against the poor-laws, rolled about the floor all day, without the inconvenience of too much food or too much clothing, under the parental superintendence of an elderly female, who received the culprits at and for the consideration of sevenpence-halfpenny per small head per week. Sevenpence-halfpenny’s worth per week is a good round diet for a child; a great deal may be got for sevenpence-halfpenny, quite enough to overload its stomach, and make it uncomfortable. The elderly female was a woman of wisdom and experience; she knew what was good for children; and she had a very accurate perception of what was good for herself. So, she appropriated the greater part of the weekly stipend to her own use, and consigned the rising parochial generation to even a shorter allowance than was originally provided for them. Thereby finding in the lowest depth a deeper still; and proving herself a very great experimental philosopher."""

    def print_out(*breaks_args, **kwargs):
        kwargs["ret_vals"] = True
        breaks = knuth_plass_breaks(*breaks_args, **kwargs)

        print()
        print("JUSTIFIED LEFT")
        print("==============")
        print(str_for_breaks(breaks, JUSTIFY.LEFT, '|'))

        print()
        print("JUSTIFIED RIGHT")
        print("===============")
        print(str_for_breaks(breaks, JUSTIFY.RIGHT, '|'))

        print()
        print("JUSTIFIED CENTER")
        print("================")
        print(str_for_breaks(breaks, JUSTIFY.CENTER, '|'))

        print()
        print("JUSTIFIED FULL")
        print("==============")
        print(str_for_breaks(breaks, JUSTIFY.FULL, '|'))
        print("----------------------------------------")

    print_out(make_paragraph(short_text), range(120, 20, -10), tolerance=1)
    print_out(make_paragraph(short_text), 100, tolerance=1)
    #print_out(make_paragraph(medium_text), 100, tolerance=1)
    #print_out(make_paragraph(medium_long_text), 100, tolerance=1) # takes a few seconds
    #print_out(make_paragraph(long_text), 100, tolerance=1) # takes a very long time

medium_long_text = \
"""Whether I shall turn out to be the hero of my own life, or whether that
station will be held by anybody else, these pages must show. To begin my
life with the beginning of my life, I record that I was born (as I have
been informed and believe) on a Friday, at twelve o’clock at night.
It was remarked that the clock began to strike, and I began to cry,
simultaneously.

In consideration of the day and hour of my birth, it was declared by
the nurse, and by some sage women in the neighbourhood who had taken a
lively interest in me several months before there was any possibility
of our becoming personally acquainted, first, that I was destined to be
unlucky in life; and secondly, that I was privileged to see ghosts and
spirits; both these gifts inevitably attaching, as they believed, to
all unlucky infants of either gender, born towards the small hours on a
Friday night.

I need say nothing here, on the first head, because nothing can show
better than my history whether that prediction was verified or falsified
by the result. On the second branch of the question, I will only remark,
that unless I ran through that part of my inheritance while I was still
a baby, I have not come into it yet. But I do not at all complain of
having been kept out of this property; and if anybody else should be in
the present enjoyment of it, he is heartily welcome to keep it.

I was born with a caul, which was advertised for sale, in the
newspapers, at the low price of fifteen guineas. Whether sea-going
people were short of money about that time, or were short of faith and
preferred cork jackets, I don’t know; all I know is, that there was but
one solitary bidding, and that was from an attorney connected with the
bill-broking business, who offered two pounds in cash, and the balance
in sherry, but declined to be guaranteed from drowning on any higher
bargain. Consequently the advertisement was withdrawn at a dead
loss--for as to sherry, my poor dear mother’s own sherry was in the
market then--and ten years afterwards, the caul was put up in a raffle
down in our part of the country, to fifty members at half-a-crown a
head, the winner to spend five shillings. I was present myself, and I
remember to have felt quite uncomfortable and confused, at a part of
myself being disposed of in that way. The caul was won, I recollect, by
an old lady with a hand-basket, who, very reluctantly, produced from it
the stipulated five shillings, all in halfpence, and twopence halfpenny
short--as it took an immense time and a great waste of arithmetic, to
endeavour without any effect to prove to her. It is a fact which will
be long remembered as remarkable down there, that she was never drowned,
but died triumphantly in bed, at ninety-two. I have understood that it
was, to the last, her proudest boast, that she never had been on the
water in her life, except upon a bridge; and that over her tea (to which
she was extremely partial) she, to the last, expressed her indignation
at the impiety of mariners and others, who had the presumption to go
‘meandering’ about the world. It was in vain to represent to her
that some conveniences, tea perhaps included, resulted from this
objectionable practice. She always returned, with greater emphasis and
with an instinctive knowledge of the strength of her objection, ‘Let us
have no meandering.’"""

long_text = \
"""Whether I shall turn out to be the hero of my own life, or whether that
station will be held by anybody else, these pages must show. To begin my
life with the beginning of my life, I record that I was born (as I have
been informed and believe) on a Friday, at twelve o’clock at night.
It was remarked that the clock began to strike, and I began to cry,
simultaneously.

In consideration of the day and hour of my birth, it was declared by
the nurse, and by some sage women in the neighbourhood who had taken a
lively interest in me several months before there was any possibility
of our becoming personally acquainted, first, that I was destined to be
unlucky in life; and secondly, that I was privileged to see ghosts and
spirits; both these gifts inevitably attaching, as they believed, to
all unlucky infants of either gender, born towards the small hours on a
Friday night.

I need say nothing here, on the first head, because nothing can show
better than my history whether that prediction was verified or falsified
by the result. On the second branch of the question, I will only remark,
that unless I ran through that part of my inheritance while I was still
a baby, I have not come into it yet. But I do not at all complain of
having been kept out of this property; and if anybody else should be in
the present enjoyment of it, he is heartily welcome to keep it.

I was born with a caul, which was advertised for sale, in the
newspapers, at the low price of fifteen guineas. Whether sea-going
people were short of money about that time, or were short of faith and
preferred cork jackets, I don’t know; all I know is, that there was but
one solitary bidding, and that was from an attorney connected with the
bill-broking business, who offered two pounds in cash, and the balance
in sherry, but declined to be guaranteed from drowning on any higher
bargain. Consequently the advertisement was withdrawn at a dead
loss--for as to sherry, my poor dear mother’s own sherry was in the
market then--and ten years afterwards, the caul was put up in a raffle
down in our part of the country, to fifty members at half-a-crown a
head, the winner to spend five shillings. I was present myself, and I
remember to have felt quite uncomfortable and confused, at a part of
myself being disposed of in that way. The caul was won, I recollect, by
an old lady with a hand-basket, who, very reluctantly, produced from it
the stipulated five shillings, all in halfpence, and twopence halfpenny
short--as it took an immense time and a great waste of arithmetic, to
endeavour without any effect to prove to her. It is a fact which will
be long remembered as remarkable down there, that she was never drowned,
but died triumphantly in bed, at ninety-two. I have understood that it
was, to the last, her proudest boast, that she never had been on the
water in her life, except upon a bridge; and that over her tea (to which
she was extremely partial) she, to the last, expressed her indignation
at the impiety of mariners and others, who had the presumption to go
‘meandering’ about the world. It was in vain to represent to her
that some conveniences, tea perhaps included, resulted from this
objectionable practice. She always returned, with greater emphasis and
with an instinctive knowledge of the strength of her objection, ‘Let us
have no meandering.’

Not to meander myself, at present, I will go back to my birth.

I was born at Blunderstone, in Suffolk, or ‘there by’, as they say in
Scotland. I was a posthumous child. My father’s eyes had closed upon
the light of this world six months, when mine opened on it. There is
something strange to me, even now, in the reflection that he never saw
me; and something stranger yet in the shadowy remembrance that I have
of my first childish associations with his white grave-stone in the
churchyard, and of the indefinable compassion I used to feel for it
lying out alone there in the dark night, when our little parlour
was warm and bright with fire and candle, and the doors of our house
were--almost cruelly, it seemed to me sometimes--bolted and locked
against it.

An aunt of my father’s, and consequently a great-aunt of mine, of whom
I shall have more to relate by and by, was the principal magnate of our
family. Miss Trotwood, or Miss Betsey, as my poor mother always called
her, when she sufficiently overcame her dread of this formidable
personage to mention her at all (which was seldom), had been married
to a husband younger than herself, who was very handsome, except in the
sense of the homely adage, ‘handsome is, that handsome does’--for he
was strongly suspected of having beaten Miss Betsey, and even of having
once, on a disputed question of supplies, made some hasty but determined
arrangements to throw her out of a two pair of stairs’ window. These
evidences of an incompatibility of temper induced Miss Betsey to pay him
off, and effect a separation by mutual consent. He went to India with
his capital, and there, according to a wild legend in our family, he was
once seen riding on an elephant, in company with a Baboon; but I think
it must have been a Baboo--or a Begum. Anyhow, from India tidings of his
death reached home, within ten years. How they affected my aunt, nobody
knew; for immediately upon the separation, she took her maiden name
again, bought a cottage in a hamlet on the sea-coast a long way off,
established herself there as a single woman with one servant, and
was understood to live secluded, ever afterwards, in an inflexible
retirement.

My father had once been a favourite of hers, I believe; but she was
mortally affronted by his marriage, on the ground that my mother was ‘a
wax doll’. She had never seen my mother, but she knew her to be not
yet twenty. My father and Miss Betsey never met again. He was double
my mother’s age when he married, and of but a delicate constitution. He
died a year afterwards, and, as I have said, six months before I came
into the world.

This was the state of matters, on the afternoon of, what I may be
excused for calling, that eventful and important Friday. I can make no
claim therefore to have known, at that time, how matters stood; or to
have any remembrance, founded on the evidence of my own senses, of what
follows.

My mother was sitting by the fire, but poorly in health, and very low in
spirits, looking at it through her tears, and desponding heavily about
herself and the fatherless little stranger, who was already welcomed by
some grosses of prophetic pins, in a drawer upstairs, to a world not at
all excited on the subject of his arrival; my mother, I say, was sitting
by the fire, that bright, windy March afternoon, very timid and sad, and
very doubtful of ever coming alive out of the trial that was before her,
when, lifting her eyes as she dried them, to the window opposite, she
saw a strange lady coming up the garden.

My mother had a sure foreboding at the second glance, that it was
Miss Betsey. The setting sun was glowing on the strange lady, over the
garden-fence, and she came walking up to the door with a fell rigidity
of figure and composure of countenance that could have belonged to
nobody else.

When she reached the house, she gave another proof of her identity.
My father had often hinted that she seldom conducted herself like any
ordinary Christian; and now, instead of ringing the bell, she came and
looked in at that identical window, pressing the end of her nose against
the glass to that extent, that my poor dear mother used to say it became
perfectly flat and white in a moment.

She gave my mother such a turn, that I have always been convinced I am
indebted to Miss Betsey for having been born on a Friday.

My mother had left her chair in her agitation, and gone behind it in
the corner. Miss Betsey, looking round the room, slowly and inquiringly,
began on the other side, and carried her eyes on, like a Saracen’s Head
in a Dutch clock, until they reached my mother. Then she made a frown
and a gesture to my mother, like one who was accustomed to be obeyed, to
come and open the door. My mother went.

‘Mrs. David Copperfield, I think,’ said Miss Betsey; the emphasis
referring, perhaps, to my mother’s mourning weeds, and her condition.

‘Yes,’ said my mother, faintly.

‘Miss Trotwood,’ said the visitor. ‘You have heard of her, I dare say?’

My mother answered she had had that pleasure. And she had a disagreeable
consciousness of not appearing to imply that it had been an overpowering
pleasure.

‘Now you see her,’ said Miss Betsey. My mother bent her head, and begged
her to walk in.

They went into the parlour my mother had come from, the fire in the best
room on the other side of the passage not being lighted--not having
been lighted, indeed, since my father’s funeral; and when they were both
seated, and Miss Betsey said nothing, my mother, after vainly trying to
restrain herself, began to cry. ‘Oh tut, tut, tut!’ said Miss Betsey, in
a hurry. ‘Don’t do that! Come, come!’

My mother couldn’t help it notwithstanding, so she cried until she had
had her cry out.

‘Take off your cap, child,’ said Miss Betsey, ‘and let me see you.’

My mother was too much afraid of her to refuse compliance with this odd
request, if she had any disposition to do so. Therefore she did as she
was told, and did it with such nervous hands that her hair (which was
luxuriant and beautiful) fell all about her face.

‘Why, bless my heart!’ exclaimed Miss Betsey. ‘You are a very Baby!’

My mother was, no doubt, unusually youthful in appearance even for her
years; she hung her head, as if it were her fault, poor thing, and said,
sobbing, that indeed she was afraid she was but a childish widow, and
would be but a childish mother if she lived. In a short pause which
ensued, she had a fancy that she felt Miss Betsey touch her hair, and
that with no ungentle hand; but, looking at her, in her timid hope, she
found that lady sitting with the skirt of her dress tucked up, her hands
folded on one knee, and her feet upon the fender, frowning at the fire.

‘In the name of Heaven,’ said Miss Betsey, suddenly, ‘why Rookery?’

‘Do you mean the house, ma’am?’ asked my mother.

‘Why Rookery?’ said Miss Betsey. ‘Cookery would have been more to the
purpose, if you had had any practical ideas of life, either of you.’

‘The name was Mr. Copperfield’s choice,’ returned my mother. ‘When he
bought the house, he liked to think that there were rooks about it.’

The evening wind made such a disturbance just now, among some tall old
elm-trees at the bottom of the garden, that neither my mother nor Miss
Betsey could forbear glancing that way. As the elms bent to one another,
like giants who were whispering secrets, and after a few seconds of such
repose, fell into a violent flurry, tossing their wild arms about, as if
their late confidences were really too wicked for their peace of mind,
some weatherbeaten ragged old rooks’-nests, burdening their higher
branches, swung like wrecks upon a stormy sea.

‘Where are the birds?’ asked Miss Betsey.

‘The--?’ My mother had been thinking of something else.

‘The rooks--what has become of them?’ asked Miss Betsey.

‘There have not been any since we have lived here,’ said my mother. ‘We
thought--Mr. Copperfield thought--it was quite a large rookery; but
the nests were very old ones, and the birds have deserted them a long
while.’

‘David Copperfield all over!’ cried Miss Betsey. ‘David Copperfield from
head to foot! Calls a house a rookery when there’s not a rook near it,
and takes the birds on trust, because he sees the nests!’

‘Mr. Copperfield,’ returned my mother, ‘is dead, and if you dare to
speak unkindly of him to me--’

My poor dear mother, I suppose, had some momentary intention of
committing an assault and battery upon my aunt, who could easily have
settled her with one hand, even if my mother had been in far better
training for such an encounter than she was that evening. But it passed
with the action of rising from her chair; and she sat down again very
meekly, and fainted.

When she came to herself, or when Miss Betsey had restored her,
whichever it was, she found the latter standing at the window. The
twilight was by this time shading down into darkness; and dimly as they
saw each other, they could not have done that without the aid of the
fire.

‘Well?’ said Miss Betsey, coming back to her chair, as if she had only
been taking a casual look at the prospect; ‘and when do you expect--’

‘I am all in a tremble,’ faltered my mother. ‘I don’t know what’s the
matter. I shall die, I am sure!’

‘No, no, no,’ said Miss Betsey. ‘Have some tea.’

‘Oh dear me, dear me, do you think it will do me any good?’ cried my
mother in a helpless manner.

‘Of course it will,’ said Miss Betsey. ‘It’s nothing but fancy. What do
you call your girl?’

‘I don’t know that it will be a girl, yet, ma’am,’ said my mother
innocently.

‘Bless the Baby!’ exclaimed Miss Betsey, unconsciously quoting the
second sentiment of the pincushion in the drawer upstairs, but
applying it to my mother instead of me, ‘I don’t mean that. I mean your
servant-girl.’

‘Peggotty,’ said my mother.

‘Peggotty!’ repeated Miss Betsey, with some indignation. ‘Do you mean to
say, child, that any human being has gone into a Christian church,
and got herself named Peggotty?’ ‘It’s her surname,’ said my mother,
faintly. ‘Mr. Copperfield called her by it, because her Christian name
was the same as mine.’

‘Here! Peggotty!’ cried Miss Betsey, opening the parlour door. ‘Tea.
Your mistress is a little unwell. Don’t dawdle.’

Having issued this mandate with as much potentiality as if she had been
a recognized authority in the house ever since it had been a house,
and having looked out to confront the amazed Peggotty coming along the
passage with a candle at the sound of a strange voice, Miss Betsey shut
the door again, and sat down as before: with her feet on the fender, the
skirt of her dress tucked up, and her hands folded on one knee.

‘You were speaking about its being a girl,’ said Miss Betsey. ‘I have no
doubt it will be a girl. I have a presentiment that it must be a girl.
Now child, from the moment of the birth of this girl--’

‘Perhaps boy,’ my mother took the liberty of putting in.

‘I tell you I have a presentiment that it must be a girl,’ returned Miss
Betsey. ‘Don’t contradict. From the moment of this girl’s birth, child,
I intend to be her friend. I intend to be her godmother, and I beg
you’ll call her Betsey Trotwood Copperfield. There must be no mistakes
in life with THIS Betsey Trotwood. There must be no trifling with HER
affections, poor dear. She must be well brought up, and well guarded
from reposing any foolish confidences where they are not deserved. I
must make that MY care.’

There was a twitch of Miss Betsey’s head, after each of these sentences,
as if her own old wrongs were working within her, and she repressed any
plainer reference to them by strong constraint. So my mother suspected,
at least, as she observed her by the low glimmer of the fire: too
much scared by Miss Betsey, too uneasy in herself, and too subdued and
bewildered altogether, to observe anything very clearly, or to know what
to say.

‘And was David good to you, child?’ asked Miss Betsey, when she had been
silent for a little while, and these motions of her head had gradually
ceased. ‘Were you comfortable together?’

‘We were very happy,’ said my mother. ‘Mr. Copperfield was only too good
to me.’

‘What, he spoilt you, I suppose?’ returned Miss Betsey.

‘For being quite alone and dependent on myself in this rough world
again, yes, I fear he did indeed,’ sobbed my mother.

‘Well! Don’t cry!’ said Miss Betsey. ‘You were not equally matched,
child--if any two people can be equally matched--and so I asked the
question. You were an orphan, weren’t you?’ ‘Yes.’

‘And a governess?’

‘I was nursery-governess in a family where Mr. Copperfield came to
visit. Mr. Copperfield was very kind to me, and took a great deal of
notice of me, and paid me a good deal of attention, and at last proposed
to me. And I accepted him. And so we were married,’ said my mother
simply.

‘Ha! Poor Baby!’ mused Miss Betsey, with her frown still bent upon the
fire. ‘Do you know anything?’

‘I beg your pardon, ma’am,’ faltered my mother.

‘About keeping house, for instance,’ said Miss Betsey.

‘Not much, I fear,’ returned my mother. ‘Not so much as I could wish.
But Mr. Copperfield was teaching me--’

[‘Much he knew about it himself!’) said Miss Betsey in a parenthesis.
--‘And I hope I should have improved, being very anxious to learn, and
he very patient to teach me, if the great misfortune of his death’--my
mother broke down again here, and could get no farther.

‘Well, well!’ said Miss Betsey. --‘I kept my housekeeping-book
regularly, and balanced it with Mr. Copperfield every night,’ cried my
mother in another burst of distress, and breaking down again.

‘Well, well!’ said Miss Betsey. ‘Don’t cry any more.’ --‘And I am
sure we never had a word of difference respecting it, except when Mr.
Copperfield objected to my threes and fives being too much like each
other, or to my putting curly tails to my sevens and nines,’ resumed my
mother in another burst, and breaking down again.

‘You’ll make yourself ill,’ said Miss Betsey, ‘and you know that will
not be good either for you or for my god-daughter. Come! You mustn’t do
it!’

This argument had some share in quieting my mother, though her
increasing indisposition had a larger one. There was an interval of
silence, only broken by Miss Betsey’s occasionally ejaculating ‘Ha!’ as
she sat with her feet upon the fender.

‘David had bought an annuity for himself with his money, I know,’ said
she, by and by. ‘What did he do for you?’

‘Mr. Copperfield,’ said my mother, answering with some difficulty, ‘was
so considerate and good as to secure the reversion of a part of it to
me.’

‘How much?’ asked Miss Betsey.

‘A hundred and five pounds a year,’ said my mother.

‘He might have done worse,’ said my aunt.

The word was appropriate to the moment. My mother was so much worse
that Peggotty, coming in with the teaboard and candles, and seeing at a
glance how ill she was,--as Miss Betsey might have done sooner if there
had been light enough,--conveyed her upstairs to her own room with all
speed; and immediately dispatched Ham Peggotty, her nephew, who had been
for some days past secreted in the house, unknown to my mother, as a
special messenger in case of emergency, to fetch the nurse and doctor.

Those allied powers were considerably astonished, when they arrived
within a few minutes of each other, to find an unknown lady of
portentous appearance, sitting before the fire, with her bonnet tied
over her left arm, stopping her ears with jewellers’ cotton. Peggotty
knowing nothing about her, and my mother saying nothing about her,
she was quite a mystery in the parlour; and the fact of her having a
magazine of jewellers’ cotton in her pocket, and sticking the article
in her ears in that way, did not detract from the solemnity of her
presence.

The doctor having been upstairs and come down again, and having
satisfied himself, I suppose, that there was a probability of this
unknown lady and himself having to sit there, face to face, for some
hours, laid himself out to be polite and social. He was the meekest of
his sex, the mildest of little men. He sidled in and out of a room, to
take up the less space. He walked as softly as the Ghost in Hamlet,
and more slowly. He carried his head on one side, partly in modest
depreciation of himself, partly in modest propitiation of everybody
else. It is nothing to say that he hadn’t a word to throw at a dog. He
couldn’t have thrown a word at a mad dog. He might have offered him one
gently, or half a one, or a fragment of one; for he spoke as slowly as
he walked; but he wouldn’t have been rude to him, and he couldn’t have
been quick with him, for any earthly consideration.

Mr. Chillip, looking mildly at my aunt with his head on one side, and
making her a little bow, said, in allusion to the jewellers’ cotton, as
he softly touched his left ear:

‘Some local irritation, ma’am?’

‘What!’ replied my aunt, pulling the cotton out of one ear like a cork.

Mr. Chillip was so alarmed by her abruptness--as he told my mother
afterwards--that it was a mercy he didn’t lose his presence of mind. But
he repeated sweetly:

‘Some local irritation, ma’am?’

‘Nonsense!’ replied my aunt, and corked herself again, at one blow.

Mr. Chillip could do nothing after this, but sit and look at her feebly,
as she sat and looked at the fire, until he was called upstairs again.
After some quarter of an hour’s absence, he returned.

‘Well?’ said my aunt, taking the cotton out of the ear nearest to him.

‘Well, ma’am,’ returned Mr. Chillip, ‘we are--we are progressing slowly,
ma’am.’

‘Ba--a--ah!’ said my aunt, with a perfect shake on the contemptuous
interjection. And corked herself as before.

Really--really--as Mr. Chillip told my mother, he was almost shocked;
speaking in a professional point of view alone, he was almost shocked.
But he sat and looked at her, notwithstanding, for nearly two hours,
as she sat looking at the fire, until he was again called out. After
another absence, he again returned.

‘Well?’ said my aunt, taking out the cotton on that side again.

‘Well, ma’am,’ returned Mr. Chillip, ‘we are--we are progressing slowly,
ma’am.’

‘Ya--a--ah!’ said my aunt. With such a snarl at him, that Mr. Chillip
absolutely could not bear it. It was really calculated to break his
spirit, he said afterwards. He preferred to go and sit upon the stairs,
in the dark and a strong draught, until he was again sent for.

Ham Peggotty, who went to the national school, and was a very dragon at
his catechism, and who may therefore be regarded as a credible witness,
reported next day, that happening to peep in at the parlour-door an hour
after this, he was instantly descried by Miss Betsey, then walking to
and fro in a state of agitation, and pounced upon before he could make
his escape. That there were now occasional sounds of feet and voices
overhead which he inferred the cotton did not exclude, from the
circumstance of his evidently being clutched by the lady as a victim on
whom to expend her superabundant agitation when the sounds were loudest.
That, marching him constantly up and down by the collar (as if he had
been taking too much laudanum), she, at those times, shook him, rumpled
his hair, made light of his linen, stopped his ears as if she confounded
them with her own, and otherwise tousled and maltreated him. This was
in part confirmed by his aunt, who saw him at half past twelve o’clock,
soon after his release, and affirmed that he was then as red as I was.

The mild Mr. Chillip could not possibly bear malice at such a time, if
at any time. He sidled into the parlour as soon as he was at liberty,
and said to my aunt in his meekest manner:

‘Well, ma’am, I am happy to congratulate you.’

‘What upon?’ said my aunt, sharply.

Mr. Chillip was fluttered again, by the extreme severity of my aunt’s
manner; so he made her a little bow and gave her a little smile, to
mollify her.

‘Mercy on the man, what’s he doing!’ cried my aunt, impatiently. ‘Can’t
he speak?’

‘Be calm, my dear ma’am,’ said Mr. Chillip, in his softest accents.

‘There is no longer any occasion for uneasiness, ma’am. Be calm.’

It has since been considered almost a miracle that my aunt didn’t shake
him, and shake what he had to say, out of him. She only shook her own
head at him, but in a way that made him quail.

‘Well, ma’am,’ resumed Mr. Chillip, as soon as he had courage, ‘I am
happy to congratulate you. All is now over, ma’am, and well over.’

During the five minutes or so that Mr. Chillip devoted to the delivery
of this oration, my aunt eyed him narrowly.

‘How is she?’ said my aunt, folding her arms with her bonnet still tied
on one of them.

‘Well, ma’am, she will soon be quite comfortable, I hope,’ returned Mr.
Chillip. ‘Quite as comfortable as we can expect a young mother to be,
under these melancholy domestic circumstances. There cannot be any
objection to your seeing her presently, ma’am. It may do her good.’

‘And SHE. How is SHE?’ said my aunt, sharply.

Mr. Chillip laid his head a little more on one side, and looked at my
aunt like an amiable bird.

‘The baby,’ said my aunt. ‘How is she?’

‘Ma’am,’ returned Mr. Chillip, ‘I apprehended you had known. It’s a
boy.’

My aunt said never a word, but took her bonnet by the strings, in the
manner of a sling, aimed a blow at Mr. Chillip’s head with it, put it on
bent, walked out, and never came back. She vanished like a discontented
fairy; or like one of those supernatural beings, whom it was popularly
supposed I was entitled to see; and never came back any more.

No. I lay in my basket, and my mother lay in her bed; but Betsey
Trotwood Copperfield was for ever in the land of dreams and shadows, the
tremendous region whence I had so lately travelled; and the light upon
the window of our room shone out upon the earthly bourne of all such
travellers, and the mound above the ashes and the dust that once was he,
without whom I had never been.
"""

if __name__ == "__main__":
    main()








