"""
Status: The algorithm works and an example of using the algorithm is finished,
    so I am done working on this module.

A module that implements the Knuth-Plass text formatting algorithm in Python.

This Impelmentation of the Knuth-Plass algorithm is much faster than the
    implementations in knuth_plass and knuth_plass2

Using the Knuth-Plass algorithm, one can beakup text into lines in such a way
    that each line has "minimum badness" as defined by the algorithm. It also
    figures out how large each space should be if you want to
    "FULL" A.K.A. "LEFT-RIGHT" justify the text.

There are 2 main parts to the algorithm:
    Part 1: Turning your text into a list of Glue, Box, and Penalty objects.
        This part is crucial as this is where you describe what your paragraph
        looks like as far as where you can break it up and how large the
        different components can be.

        A 'KnuthPlassParagraph' (which is just a list of Glue, Box, and Penalty
            objects) is made up of 3 things.

            Glue:    The spaces that can have varibale width. Have a default
                width, but can shrink by `shrink` amount and stretch by
                `stretch` amount.

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
from typing import List, Callable, Union, Dict, Generator, Any
from collections import namedtuple
from tools import profile

class JUSTIFY:
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    FULL = "FULL"

WHITESPACE_CHARS = ' \t\r\n\f\v'
WHITESPACE = set(ch for ch in WHITESPACE_CHARS)
Num = Union[int, float]
INF = 10000
GLUE, BOX, PENALTY = 1, 2, 3

# =============================================================================
# Specifications (Glue, Box, Penalty)
# -----------------------------------------------------------------------------

class Specification:
    # Specify default values
    t       = default_t       = None # t in the paper; the type of the Spec
    width   = default_width   = 0.0  # w in the paper; the ideal width of the glue, the width of added typeset material for the penalty, or the static width of the box
    stretch = default_stretch = 0.0  # y in the paper; the amount this glue can stretch/enlarge its width by
    shrink  = default_shrink  = 0.0  # z in the paper; the amount this glue can shrink its width by
    penalty = default_penalty = 0.0  # p in the paper; the amount to be penalized if use this penalty
    flagged = default_flagged = 0    # f in the paper; used to say whether a hyphen will need to be put here. Is either 1 for True or 0 for False

    def is_glue(self):         return False
    def is_box(self):          return False
    def is_penalty(self):      return False
    def is_forced_break(self): return False

class Glue(Specification):
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
        if r < 0:
            # As r is negative, will be subtracting width
            return self.width + (r * self.shrink)
        else:
            # r is positive, so will be adding width (or r is 0 and so adding nothing)
            return self.width + (r * self.stretch)

    def is_glue(self): return True

    def copy(self):
        return Glue(self.shrink, self.width, self.stretch)

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width}, stretch={self.stretch}, shrink={self.shrink})>'

class Box(Specification):
    """
    A box refers to something that is to be typeset: either a character from
        some font of type, or a black rectangle such as a horizontal or
        vertical rule, or something built up from several characters such as an
        accented letter or a mathematical formula. The contents of a box may be
        extremely complicated, or they may be extremely simple; the
        line-breaking algorithm does not peek inside a box to see what it
        contains, so we may consider the boxes to be sealed and locked.
    """
    __slots__ = ['width']
    t = BOX

    def __init__(self, width:Num):
        self.width: Num = width # The fixed width of the box (so width of what is in the box with that actualy value being stored in the KnuthPlassParagraph alongside it)

    def is_box(self): return True

    def copy(self):
        return Box(self.width)

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width})>'

class Penalty(Specification):
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

    def is_penalty(self): return True
    def is_forced_break(self): (self.penalty >= INF)

    def copy(self):
        return Penalty(self.width, self.penalty, self.flagged)

    def __repr__(self):
        return f'<{self.__class__.__name__}(width={self.width}, penalty={self.penalty}, flagged={self.flagged})>'

Spec = Union[Glue, Box, Penalty]

# =============================================================================
# Helper Class for KnuthPlassParagraph
# -----------------------------------------------------------------------------

class Break:
    """
    A class representing a break in the text as calculated by the Knuth-Plass
    algorithm.
    """
    __slots__ = ["position", "line", "fitness_class", "demerits", "ratio", "desired_line_length", "previous"]
    def __init__(self, position:int, line:int, fitness_class:int, demerits:float, ratio:float, desired_line_length:float, previous=None):
        self.position      = position      # Index in the Knuth-Plass paragraph this break occurs (excludes i in last line, includes i on this current line)
        self.line          = line          # What line of the resulting paragraph this break creates
        self.fitness_class = fitness_class # The fitness class of this break
        self.demerits      = demerits      # How 'bad' this break is
        self.ratio         = ratio         # The ratio used to get the actual width of glues for this line if trying to full justify the line
        self.desired_line_length = desired_line_length # The line length that this line is supposed to be if all glues are expanded by the adjustment ratio `ratio`
        self.previous      = previous      # The previous break that had to occur to get this one

    def key(self):
        return (self.line, self.fitness_class, self.position)

    def copy(self):
        return Break(self.position, self.line, self.fitness_class, self.demerits, self.ratio, self.previous)

    def __repr__(self):
        return f"<{self.__class__.__name__}(pos={self.position}, line={self.line}, fitness_class={self.fitness_class}, demerits={self.demerits}, ratio={self.ratio}, desired_line_length={self.desired_line_length})>"

# =============================================================================
# KnuthPlassParagraph Class
# -----------------------------------------------------------------------------

class KnuthPlassParagraph:
    def __init__(self):

        # These two are parralel arrays. One holds the spec for each placement
        # in the paragraph and the other holds the value for it. The reason for
        # this is that te specs are not changed by the algorithm EVER. This
        # means that you could save on memory by creating only one glue object
        # for spaces and just use that same object for every single space.
        # Meanwhile, values will probably be different for every single Spec,
        # so they are kept in a seperate array to facilitate that and still
        # have all the Spec objects be reusable
        self.specs = []
        self.vals  = []

        # Populated by calc_knuth_plass_breaks
        self.sum_width = None
        self.sum_shrink = None
        self.sum_stretch = None

    # -------------------------------------------------------------------------
    # Methods used in manipulating the paragraph before you calculate the knuth_plass_breaks

    def __len__(self):
        return len(self.specs)

    def pop(self, index=None):
        if index is None:
            return (self.specs.pop(), self.vals.pop())
        else:
            return (self.specs.pop(index), self.vals.pop(index))

    def append(self, spec:Spec, value:Any):
        self.specs.append(spec)
        self.vals.append(value)

    def append_std_end(self):
        """
        Appends the standard end to any paragraph.
        """
        ends = \
           [Penalty(0,  INF,   0), # Forced non-break (must not break here, otherwise a Box coming before the Glue after this would allow a break to be here)
            Glue(   0,    0, INF), # Glue that fills the rest of the last line (even if that fill is 0 width)
            Penalty(0, -INF,   1)] # Forced break (Ends last line)
        self.specs.extend(ends)
        self.vals.extend([None, None, None])

    # -------------------------------------------------------------------------
    # Methods used in the KnuthPlass breaks algorithm

    def is_feasible_breakpoint(self, i:int):
        """
        Return true if position 'i' is a feasible breakpoint.
        """
        spec = self.specs[i]
        if spec.t == PENALTY and spec.penalty < INF:
            # Specified breakpoint
            return 1
        elif i > 0 and self.specs[i-1].t == BOX and spec.t == GLUE:
            # Breakpoint when glue directly follows a box
            return 1
        else:
            return 0

    @profile()
    def calc_knuth_plass_breaks(self,
            line_lengths:Union[List[Num], Num, \
                    Generator[Num, None, None]], # l1, l2,... in the paper
            looseness:int=0,                     # q in the paper
            tolerance:int=1,                     # rho in the paper
            fitness_demerit:Num=100,             # gamma in the paper
            flagged_demerit:Num=100,             # alpha in the paper
        ):
        """
        Runs the Knuth-Plass breaks algorithm to calculate the optimal break
            points for this KnuthPlassParagraph based on the given line_lengths

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
        """
        paragraph = self.specs # Only the specs are needed for the actual algorithm

        if isinstance(line_lengths, int) or isinstance(line_lengths, float):
            line_lengths = [line_lengths]

        m = len(paragraph)
        if m == 0: return [] # No text, so no breaks

        # Precompute the running sums of width, stretch, and shrink (W,Y,Z in the
        # original paper).  These make it easy to measure the width/stretch/shrink
        # between two indexes; just compute sum_*[pos2] - sum_*[pos1].  Note that
        # sum_*[i] is the total up to but not including the box at position i.
        sum_width = [0] * m; sum_stretch = [0] * m; sum_shrink  = [0] * m
        width_sum = stretch_sum = shrink_sum = 0.0
        for i, spec in enumerate(paragraph):
            sum_width[i] = width_sum
            sum_stretch[i] = stretch_sum
            sum_shrink[i] = shrink_sum

            width_sum += spec.width
            stretch_sum += spec.stretch
            shrink_sum  += spec.shrink

        def compute_adjustment_ratio(pos1, pos2, line, line_lengths):
            """
            Compute adjustment ratio for the line between pos1 and pos2.

            This is how much you would have to shrink (if r < 0) or
                stretch (if r > 0) the line we are currently looking at in order to
                make it exactly fit exactly the current line (make it have the same
                exact same length as the current line).
            """
            ideal_width =  sum_width[pos2] - sum_width[pos1] # ideal width

            if paragraph[pos2].t == PENALTY:
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
                y = sum_stretch[pos2] - sum_stretch[pos1] # The total amount of stretch (in whatever units all the parts of the paragraph are measured in) you can stretch this line by

                if y > 0:
                    # Since it is possible to stretch the line, found out how much
                    #   you should stretch it by to take up the full width of the line
                    r = (available_width - ideal_width) / float(y)
                else:
                    r = INF

            elif ideal_width > available_width:
                # Must shrink the line by removing space from glue if you want it
                #   to fit on the line
                z = sum_shrink[pos2] - sum_shrink[pos1] # Total amount you could possibly shrink this line by to make it fit on the current desired line

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

            return r, available_width

        A = Break(position=0, line=0, fitness_class=1, demerits=0, ratio=1, desired_line_length=None)

        # Keep breaks sorted by their line numbers (the actual sorting happens
        #   in active_nodes_gen when the line numbers are sorted and used to
        #   access the dict)
        active_nodes = {A.line: [A]}

        # Used to easily see if a node is already accounted for so that we do
        #   not look at the same Break twice
        active_nodes_set = {A.key()}

        def add_active_node(node):
            """
            Adds an active node to the active nodes.
            """
            if node.key() in active_nodes_set:
                return

            node_line = node.line

            if node_line in active_nodes:
                active_nodes[node_line].insert(0, node)
            else:
                active_nodes[node_line] = [node]

            active_nodes_set.add(node.key())

        def remove_active_node(node):
            """
            Removes an active node from the active nodes.
            """
            nodes = active_nodes[node.line]
            nodes.remove(node)

            if len(nodes) == 0:
                active_nodes.pop(node.line)

            active_nodes_set.remove(node.key())

        def active_nodes_gen():
            """
            Yields the active nodes in the order they would be if they were in
                a normal list.
            """
            for line_num in sorted(active_nodes.keys()):
                for node in active_nodes[line_num]:
                    yield node
        # -- End Function

        breaks_to_deactivate = [] # List of breaks that were feasible but no longer are
        breaks_to_activate   = [] # List of newly-found feasible breaks
        for i, B in enumerate(paragraph):
            # Determine if this box is a feasible breakpoint and
            # perform the main loop if it is.
            if self.is_feasible_breakpoint(i):
                # Loop over the list of active nodes, and compute the fitness
                # of the line formed by breaking at A and B
                for A in active_nodes_gen():
                    r, desired_line_length = compute_adjustment_ratio(A.position, i, A.line, line_lengths)

                    if (r < -1 or B.penalty >= INF):
                        # Deactivate node A
                        breaks_to_deactivate.append(A)

                    if -1 <= r <= tolerance:
                        # Compute demerits and fitness class
                        if B.penalty >= 0:
                           demerits = (1 + 100 * abs(r)**3 + B.penalty) ** 3
                        elif B.penalty <= -INF: # Forced break point
                           demerits = (1 + 100 * abs(r)**3) ** 2 - B.penalty**2
                        else:
                           demerits = (1 + 100 * abs(r)**3) ** 2

                        # two consecutive breaks with flagged demerits causes an
                        # additional demerit to be added (don't want two lines with
                        # with a hyphen at the end of them)
                        if B.flagged and paragraph[A.position].flagged:
                            demerits += flagged_demerit

                        # Figure out the fitness class of this line
                        if   r < -.5: fitness_class = 0 # tight line
                        elif r <= .5: fitness_class = 1 # normal line
                        elif r <= 1:  fitness_class = 2 # loose line
                        else:         fitness_class = 3 # very loose line

                        # If two consecutive lines are in very different fitness
                        # classes, add to the demerit score for this break.
                        if abs(fitness_class - A.fitness_class) > 1:
                            demerits += fitness_demerit

                        # Record a feasible break from A to B
                        brk = Break(
                                position      = i,
                                line          = A.line + 1,
                                fitness_class = fitness_class,
                                demerits      = demerits,
                                ratio         = r,
                                desired_line_length = desired_line_length,
                                previous      = A
                            )
                        breaks_to_activate.append(brk)
                # end for A in active_nodes

                # Deactivate nodes that need to be deactivated
                for node in breaks_to_deactivate:
                    if len(active_nodes) > 1:
                        remove_active_node(node)
                    else:
                        break
                breaks_to_deactivate.clear()

                # Activate the new nodes that need to be activated
                for node in breaks_to_activate:
                    add_active_node(node)
                breaks_to_activate.clear()

            # end if self.feasible_breakpoint()
        # end for i in range(m)

        active_nodes = [node for node in active_nodes_gen()]

        # For some reason, some of the active_nodes that reach this point do not
        #   represent a break at the very end of the paragraph so only consider
        #   ending breakpoints that actually include the ending line of the
        #   paragraph
        for node in active_nodes[:]:
            if node.position != len(paragraph) - 1:
                active_nodes.remove(node)

        assert len(active_nodes) > 0, \
                'Could not find any set of beakpoints that both met the given criteria and ended at the end of the paragraph.'

        # Find the active node with the lowest number of demerits.
        A = min(active_nodes, key=lambda A: A.demerits)

        if looseness != 0:
            # The search for the appropriate active node is a bit more complicated;
            # we look for a node with a paragraph length that's as close as
            # possible to (A.line + looseness) with the minimum number of demerits.

            best = 0
            d = INF
            for br in active_nodes:
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

        # -- Generate the list of chosen break points
        breaks = []
        while A is not None:
            breaks.append(A)
            A = A.previous
        breaks.reverse()
        breaks.pop(0) # Ignore first break because it is break that started this paragraph, not first break in paragaph

        # -- Return the results
        return breaks

    # -------------------------------------------------------------------------
    # Methods to use after calc_knuth_plass_breaks has been run

    def line_contents(self, brk:Break):
        """
        Yields the spec and val for each position specified by the given line
            break line specified by the given break.
        """
        # Only include brk.position (the last item in the line) in the line if
        # it is a penalty item--because in that case it is probably specifying
        # a hyphen; otherwise it would be a Glue at the end the line (otherwise
        # end of the line broke at a space)
        end = brk.position + 1 if self.specs[brk.position].t == PENALTY else brk.position

        start = brk.previous.position

        # Can't start a line with penalty or glue
        while self.specs[start].t in (PENALTY, GLUE) and start < end:
            start += 1

        for i in range(start, end):
            yield self.specs[i], self.vals[i]

# =============================================================================
# Methods showing of how to use the KnuthPlassParagraph
# -----------------------------------------------------------------------------

def make_paragraph(text):
    """
    An example function that takes in text and returns a paragraph from it that
        can be used in the Knuth-Plass Algorithm.
    """
    # Create the paragraph that we will be using to describe the text as a paragraph
    par = KnuthPlassParagraph()

    # This is the glue that will be used to represent all the spaces in the paragraph
    #   It's 2 units +/- 1 wide so spaces can be anywhere from 1 to 3 units wide.
    space_glue = Glue(1, 2, 1)

    # Spec used when forcing a break because the penalty is -infinity bad (so infinitely good)
    forced_break_penalty = Penalty(0, -INF, False)

    # Spec used when forcing a break to NOT occur since breaking here would be infinitely bad
    unallowed_break = Penalty(0, INF, False)

    # Box representing each and every character since, in this case, every
    # character is 1 unit wide. If they varied in width, then this would need
    # to be different for each one
    char_box = Box(1)

    for ch in text:
        if ch in ' \n':
            # Add the space between words
            par.append(space_glue, ' ')
        elif ch == '@':
            # Append forced break
            par.append(forced_break_penalty, '')

        elif ch == '~':
            # Append unallowed break
            par.append(unallowed_break, '')

        else:
            # All characters are 1 unit wide
            par.append(char_box, ch)

    # Append standard way to end the paragraph
    par.append_std_end()

    return par

def insert_spaces(string, num_spaces):
    """
    Inserts the given number of spaces into the given string, trying to put
        them inbetween words from the left side to the right.
    """
    from random import randint
    while True:

        out = ''
        added_space = False
        add_space = False # used to make sure that we only add whitespace to where there was already whitespace
        for ch in string:
            if num_spaces > 0 and add_space == True and ch in WHITESPACE:
                if randint(0, 1): # 50% chance to add space here
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

    return out


def str_for_breaks(par, breaks, justify:str=JUSTIFY.LEFT, end_mark:str=''):
    """
    Takes what is returned by the knuth_plass_breaks() function and turns it
        into a string depending on the given justification.
    """
    justify = justify.upper() # Justify constants are all upper-case, so make sure this matches as long as same word used

    total_num_lines = len(breaks)

    out = ''
    curr_line = ''
    for brk in breaks:
        line_num    = brk.line
        ratio       = brk.ratio
        line_length = brk.desired_line_length

        # -- Build the current line
        for spec, val in par.line_contents(brk):
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
                curr_line += val # This assumes that the value is a string character

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
            curr_line = curr_line.strip() # May have whitespace on ends because of glues
            curr_line = insert_spaces(curr_line, line_length - len(curr_line))
            out += curr_line
        else:
            raise Exception(f"Gave unknown justification specification: {justify}")

        curr_line = ''
        out += end_mark + "\n"
    return out

# =============================================================================
# Main
# -----------------------------------------------------------------------------

def main():
    short_text = """Among other public buildings in a certain town, which for many reasons it will be prudent to refrain from mentioning, and to which I will assign no fictitious name, there is one anciently common to most towns, great or small: to wit, a workhouse; and in this workhouse was born; on a day and date which I need not trouble myself to repeat, inasmuch as it can be of no possible consequence to the reader, in this stage of the business at all events; the item of mortality whose name is prefixed to the head of this chapter."""
    medium_text = """For the next eight or ten months, Oliver was the victim of a systematic course of treachery and deception. He was brought up by hand. The hungry and destitute situation of the infant orphan was duly reported by the workhouse authorities to the parish authorities. The parish authorities inquired with dignity of the workhouse authorities, whether there was no female then domiciled in “the house” who was in a situation to impart to Oliver Twist, the consolation and nourishment of which he stood in need. The workhouse authorities replied with humility, that there was not. Upon this, the parish authorities magnanimously and humanely resolved, that Oliver should be “farmed,” or, in other words, that he should be dispatched to a branch-workhouse some three miles off, where twenty or thirty other juvenile offenders against the poor-laws, rolled about the floor all day, without the inconvenience of too much food or too much clothing, under the parental superintendence of an elderly female, who received the culprits at and for the consideration of sevenpence-halfpenny per small head per week. Sevenpence-halfpenny’s worth per week is a good round diet for a child; a great deal may be got for sevenpence-halfpenny, quite enough to overload its stomach, and make it uncomfortable. The elderly female was a woman of wisdom and experience; she knew what was good for children; and she had a very accurate perception of what was good for herself. So, she appropriated the greater part of the weekly stipend to her own use, and consigned the rising parochial generation to even a shorter allowance than was originally provided for them. Thereby finding in the lowest depth a deeper still; and proving herself a very great experimental philosopher."""

    def print_out(par, *breaks_args, **kwargs):
        breaks = par.calc_knuth_plass_breaks(*breaks_args, **kwargs)

        print()
        print("JUSTIFIED LEFT")
        print("==============")
        print(str_for_breaks(par, breaks, JUSTIFY.LEFT, '|'))

        print()
        print("JUSTIFIED RIGHT")
        print("===============")
        print(str_for_breaks(par, breaks, JUSTIFY.RIGHT, '|'))

        print()
        print("JUSTIFIED CENTER")
        print("================")
        print(str_for_breaks(par, breaks, JUSTIFY.CENTER, '|'))

        print()
        print("JUSTIFIED FULL")
        print("==============")
        print(str_for_breaks(par, breaks, JUSTIFY.FULL, '|'))
        print("----------------------------------------")

    # The algorithm will lay out the paragraph in the OPTIMAL way, considering
    #   all possible line breaks to fit the text best in the given line
    #   widths
    print_out(make_paragraph(medium_long_text), 100, tolerance=1)

    # The algorithm can vary up the line lengths
    print_out(make_paragraph(short_text), range(120, 20, -10), tolerance=1)

    # If the algorithm needs more lines than line-lengths provided, it will
    #   repeat the last line-length specified for all subsequent lines
    print_out(make_paragraph(short_text), [100, 90, 80], tolerance=2)

    # It can also handle longer texts
    #print_out(make_paragraph(medium_long_text), 100, tolerance=2)

    # And super long texts (although it may take a few seconds)
    #print_out(make_paragraph(medium_long_text * 4), 100, tolerance=2)


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

if __name__ == "__main__":
    main()



