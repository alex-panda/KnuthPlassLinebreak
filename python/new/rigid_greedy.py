"""
Implements the code for a rigid greedy line-break algorithm i.e. an algorithm
    for text where it is assumed every character (including spaces) is exactly
    1 character long.
"""
from io import StringIO
import random
from typing import Callable, Final, List, Literal, Tuple, Union
import math

def text_len(text:List[str]) -> int:
    cnt = 0
    for t in text: cnt += len(t)
    return cnt

def never_break_word(word:str) -> List[str]:
    """
    Cut the word into a list of syllables. For default one, just return the word
        itself so that no word is ever broken up (unless it has to be because
        even on the line by itself it is too long).
    """
    return [word]


def rigid_greedy_break(
        text:Union[str, List[str]],
        width:int,
        end_line_break_word:Callable[[str], List[str]]=never_break_word,
        empty_line_break_word:Callable[[str], List[str]]=never_break_word,
        hyphen_char:str='-',
    ) -> List[List[str]]:
    """
    Breaks lines greadily, assuming that all characters (including spaces) are
        exactly 1 unit long (that's why it is rigid). The broken up paragraph
        is returned as a list of lists of strings, where each inner list is a
        list of the words (including hyphens) that would make up the line of
        text.

    text: The text of the paragraph to greedy-break in the form of a list of the
        words in the paragraph. If a string is given, it will be split on
        whitespace, otherwise every string in the given list of strings is assumed
        to be 1 word and no part of it will be changed and/or removed.

    width: The inclusive width to fit the text in i.e. if width = 50 then the
        max length of any line (with 1 space between the words of the line) will
        be 50 characters.

    end_line_break_word: Breaks the given word up into a list of substrings at
        feasible breakpoints of the word. For example, "mistletoe" could be
        broken into ["mist", "le", "toe"] in which case the largest prefix
        (No prefix on this line or "mist-" or "mistle-") of these will be used
        to end the current line and the rest will be on the proceeding line(s).

    empty_line_break_word: Same as end_line_break_word except for empty lines.
        The reason this is seperate is in case you want to break words
        differently at the end of a line as opposed to when it is the only
        word on the line i.e. you could break a word if it has to be in order
        to fit alone on a line but not break it otherwise.

        Note: If a break gives a substring that is too long to fit even by itself
            on its own line, a backup method is used which breaks it up into
            characters instead. This allows edge cases like width = 1 (only 1
            character per line) or width = 2 (only 1 character and a hyphen per
            line) to be handled.

    hyphen_char: The character(s) to use as hyphens (if want no hyphens, use '',
        if want more than 1 char per hyphen, can use longer string).
    """
    assert width >= 0, f'Unable To Break Text: The width must be at least 1, not {width}.'

    space:Final[Literal[1]] = 1 # constant used instead of magic number

    words:List[str] = text.split() if isinstance(text, str) else text

    lines:List[List[str]] = [] # each inner list is one line of words, each seperated by spaces
    curr_line:List[str] = []
    curr_line_len:int = 0

    hyphen_char_len = len(hyphen_char)

    def new_line():
        nonlocal lines
        nonlocal curr_line
        nonlocal curr_line_len

        lines.append(curr_line)
        curr_line = []
        curr_line_len = 0

    def next_syl(syls:List[str], width:int) -> Tuple[str, List[str]]:
        """
        Turns the given list of syllables into a tuple containing
            the first number of syllables it could fit in the given
            width and then the list of strings that is everything leftover
            after the syllables.
        
        Raises AssertionError if any syllable alone on a line cannot fit in the
            given width.
        """
        nonlocal hyphen_char_len
        nonlocal hyphen_char

        out = ''
        for i, syl in enumerate(syls):
            last = (i == (len(syls) - 1)) # if last syllable

            hyphen = 0 if last else hyphen_char_len # no hyphen on last syllable

            if len(syl) + hyphen > width:
                # Cannot fit the current syllable in the given width

                if len(out) > 0:
                    # There was already a syllable so just return it and all extra text
                    return out + hyphen_char, syls[i:]
                else:
                    # Even just this syllable, on it's own, cannot fit in the given
                    # width
                    raise AssertionError()
            elif len(out) > 0:
                # There is a previous syllable that we are adding to

                if len(out) + len(syl) + hyphen > width:
                    # The current syllable cannot be added to the last one, so
                    # return the syllable plus the remaining syllables
                    return out + hyphen_char, syls[i:]
                else:
                    out += syl
            else:
                # The current syllable fits on the line
                out += syl
        
        return out, []

    def add_syllables(word:str, break_word:Callable[[str], List[str]]):
        """
        Adds the syllables of the given word to the paragraph or raises
            an AssertionError if it was unable to.
        """
        nonlocal lines
        nonlocal curr_line
        nonlocal curr_line_len

        next_lines:List[List[str]] = []
        syls_remaining = break_word(word)

        if len(curr_line) > 0:
            # There are words already on the current line so try to add to that
            # line
            space_left = width - (curr_line_len + space)

            try:
                syl, syls_remaining = next_syl(syls_remaining, space_left)

                if len(syls_remaining) == 0:
                    # All syllables were used and can be put on current line so
                    # just return after adding them to the current line
                    curr_line.append(syl)
                    curr_line_len += len(syl)
                    return
                else:
                    # More syllables to add after this one was added to the line
                    next_lines.append([*curr_line, syl])
                    must_clear_line = True

            except AssertionError:
                # The syls_remaining are unchanged so add content of current
                # line then continue onward to handle the syllables on a new,
                # empty line
                next_lines.append(curr_line)

        # Now, add rest of syllables to new lines
        while True:

            # next_syl will raise AssertionError if could not fit a
            # syllable on the line
            next_syllable, syls_remaining = next_syl(syls_remaining, width)

            next_lines.append([next_syllable])

            if len(syls_remaining) == 0:
                break

        # Successfully added syllables

        lines.extend(next_lines[:-1])
        curr_line = next_lines[-1]
        curr_line_len = text_len(curr_line)

    def add_word(word:str):
        """
        Adds the given word to the current line or next line or next few lines
            (depending on how much it needs to be cut up to fit the current width).
        """
        nonlocal lines
        nonlocal curr_line
        nonlocal curr_line_len
        nonlocal hyphen_char
        nonlocal hyphen_char_len
        word_len = len(word)

        if len(curr_line) == 0:
            # There is nothing else on the current line

            if word_len > width:
                # Word itself is too long for the width so put pieces of it onto
                # line instead

                try:
                    add_syllables(word, empty_line_break_word)
                except AssertionError:
                    # Could not add syllables as they are -- at least one was
                    # too long for the width of the screen. Just add as much text
                    # at a time as possible because breaking it into syllables
                    # isn't enough -- have to break it down more

                    if width <= hyphen_char_len:
                        # Not enough width for hyphens so just ignore them and
                        # put as much of the word on each line as possible
                        curr_i = 0
                        word_len = len(word)
                        while curr_i < word_len:
                            next_i = min(curr_i + width, word_len)
                            lines.append([word[curr_i:next_i]])
                            curr_i = next_i
                    else:
                        # Enough width for hyphens between text

                        curr:str = word
                        while True:
                            no_hyphen_width = len(curr) - (len(curr) - width)
                            with_hyphen_width = no_hyphen_width - hyphen_char_len
                            use_hyphen = False

                            # If, without the hyphen, you can fit the rest of
                            # the current string then fit the rest of the
                            # current string, otherwise fit as much as possible
                            # with a hyphen after it
                            if no_hyphen_width >= len(curr) and curr_line_len + no_hyphen_width <= width:
                                i = min(no_hyphen_width, len(curr))
                            else:
                                i = with_hyphen_width
                                use_hyphen = True

                            prefix, suffix = curr[:i], curr[i:]

                            if len(suffix) > 0:
                                curr_line.append(prefix + (hyphen_char * use_hyphen))
                                new_line()
                            else:
                                curr_line.append(prefix)
                                curr_line_len += len(prefix)
                                break
                            curr = suffix

            else:
                # Word can be appended to the current line, perhaps as sole word
                # on the line
                curr_line.append(word)
                curr_line_len += word_len
        else:
            # There are other words on the line already

            if curr_line_len + space + word_len > width:
                # Cannot add it to the current line as one piece with 1 space
                # before it so cut it up into syllables
                try:
                    add_syllables(word, end_line_break_word)
                except AssertionError:
                    new_line()
                    add_word(word)
                    return

            else:
                # Can add it to the line in one piece
                curr_line.append(word)
                curr_line_len += space + word_len

    for word in words:
        add_word(word)

    if len(curr_line) > 0:
        lines.append(curr_line)

    return lines


# -----------------------------------------------------------------------------
# Format Methods
# =============================================================================


def rigid_left_justify(paragraph:List[List[str]], width:int, space_char:str=' ', fill_char:str=' ', line_end:str='\n') -> str:
    """
    Left justifies the given paragraph.
    """
    text = StringIO()
    for line in paragraph:
        line_str = space_char.join(line)
        text.write(line_str + (fill_char * (width - len(line_str))) + line_end)
    return text.getvalue()


def rigid_right_justify(paragraph:List[List[str]], width:int, space_char:str=' ', fill_char:str=' ', line_end:str='\n') -> str:
    """
    Right justifies the given paragraph.
    """
    text = StringIO()
    for line in paragraph:
        line_str = space_char.join(line)
        text.write((fill_char * (width - len(line_str))) + line_str + line_end)
    return text.getvalue()

def rigid_center_justify(paragraph:List[List[str]], width:int, space_char:str=' ', fill_char:str=' ', line_end:str='\n', bias_left:bool=True) -> str:
    """
    Center justifies the given paragraph.

    bias: On lines where the text cannot be exactly centered, this dictates
        whether to put the extra whitespace on the left or right of the text.
        If not biased right, then the whitespace will be biased left.
    """
    text = StringIO()
    for line in paragraph:
        line_str = space_char.join(line)
        fill = (fill_char * (width - len(line_str)))

        # Add fill either biased right or left
        if bias_left:
            fill_i = len(fill) // 2
        else:
            # bias right
            fill_i = math.ceil(len(fill) / 2)

        text.write(fill[:fill_i] + line_str + fill[fill_i:] + line_end)
    return text.getvalue()


def rigid_left_right_justify(paragraph:List[List[str]], width:int, space_char:str=' ', fill_char:str=' ', line_end:str='\n', bias:Literal['left', 'right', 'random', 'true_random']='random') -> str:
    """
    Left-right justifies the given paragraph.

    bias: Sometimes, there is extra whitespace that needs to go between words of
        a line (i.e. there are 5 words on a line, thus 4 positions for whitespace between
        them [and thus 4 required spaces because at least 1 whitespace is needed
        per position], but the line happens to need 7 spaces to make itself as
        long as the width). The bias determines how the extra whitespace is
        added to the line. A 'left' bias will cause extra whitespace to be added
        to whitespace positions from left to right, a 'right' bias will cause
        extra whitespace to be added from right to left, and 'random' will randomly
        distribute the extra whitespace among the possible positions.

    """
    text = StringIO()
    for i, line in enumerate(paragraph):

        if i == len(paragraph) - 1:
            # left-justify last line
            text.write(rigid_left_justify([line], width, space_char, fill_char, line_end))
        else:
            # not last line so properly left-right justify it
            fill_len = (width - text_len(line)) # how many fill characters in total there need to be for this line
            num_positions = len(line) - 1 # positions that can be filled with whitespace
            start_spaces_per_pos = (fill_len // num_positions)
            positions:List[str] = [space_char * start_spaces_per_pos] * num_positions # the positions of whitespace between words
            fill_len_left = fill_len - (start_spaces_per_pos * num_positions) # how much more length there is to fill

            if num_positions > 0:
                if bias == 'random':
                    while fill_len_left > 0:
                        unused = [i for i in range(len(positions))]

                        while len(unused) > 0:
                            i = unused.pop(random.randint(0, len(unused) - 1))
                            positions[i] += space_char
                            fill_len_left -= 1

                            if fill_len_left <= 0:
                                break

                elif bias == 'left':
                    while fill_len_left > 0:
                        for i in range(len(positions)):
                            if fill_len_left <= 0: break

                            positions[i] += space_char
                            fill_len_left -= 1

                elif bias == 'right':
                    while fill_len_left > 0:
                        for i in range(len(positions) - 1, -1, -1):
                            if fill_len_left <= 0: break

                            positions[i] += space_char
                            fill_len_left -= 1

                else:
                    raise AssertionError(f'Unknown bias option "{bias}"')

            positions.append('') # so that the number of positions is same length as line for the zip() function

            for word, space_chars in zip(line, positions):
                text.write(word)
                text.write(space_chars)

            text.write(line_end)

    return text.getvalue()


def rigid_justify(paragraph:List[List[str]], width:int, justify:Literal['left', 'right', 'center', 'justified']='justified', space_char:str=' ', fill_char:str=' ', line_end:str='\n') -> str:
    """
    Justifies and returns the given paragraph as a string, assuming that it is
        rigid text i.e. every character (including spaces and fill) is 1
        character long.
    """
    if   justify == 'left':
        return rigid_left_justify(paragraph, width, space_char, fill_char, line_end)
    elif justify == 'right':
        return rigid_right_justify(paragraph, width, space_char, fill_char, line_end)
    elif justify == 'center':
        return rigid_center_justify(paragraph, width, space_char, fill_char, line_end)
    elif justify == 'justified':
        return rigid_left_right_justify(paragraph, width, space_char, fill_char, line_end)
    else:
        raise AssertionError(f'Illegal Format Error: justify="{justify}" is an unknown justification option')


def main():
    test_text = """
        Although I am not disposed to maintain that the being born in a
        workhouse, is in itself the most fortunate and enviable circumstance
        that can possibly befall a human being, I do mean to say that in this
        particular instance, it was the best thing for Oliver Twist that could
        by possibility have occurred. The fact is, that there was considerable
        difficulty in inducing Oliver to take upon himself the office of
        respiration: a troublesome practice, but one which custom has rendered
        necessary to our easy existence; and for some time he lay gasping on a
        little flock mattress, rather unequally poised between this world and
        the next: the balance being decidedly in favour of the latter. Now, if,
        during this brief period, Oliver had been surrounded by careful
        grandmothers, anxious aunts, experienced nurses, and doctors of
        profound wisdom, he would most inevitably and indubitably have been
        killed in no time. There being nobody by, however, but a pauper old
        woman, who was rendered rather misty by an unwonted allowance of beer;
        and a parish surgeon who did such matters by contract; Oliver and
        Nature fought out the point between them. The result was, that, after a
        few struggles, Oliver breathed, sneezed, and proceeded to advertise to
        the inmates of the workhouse the fact of a new burden having been
        imposed upon the parish, by setting up as loud a cry as could
        reasonably have been expected from a male infant who had not been
        possessed of that very useful appendage, a voice, for a much longer
        space of time than three minutes and a quarter.
    """
    def rand_syl_sep(word:str) -> List[str]:
        import random

        last_i = 0
        out = []

        while last_i < len(word):
            curr_i = random.randint(last_i + 1, len(word))
            out.append(word[last_i:curr_i])
            last_i = curr_i

        return out

    width = 100
    space_char = ' '
    fill_char = ' '
    par = rigid_greedy_break(test_text, width, rand_syl_sep, rand_syl_sep, '-')

    _max_len = 0
    def max_len(res:str):
        nonlocal _max_len
        _max_len = max(max(len(line) for line in res.split('\n')), _max_len)

    print()
    print(rigid_center_justify([["__Rigid Greedy Break__"]], width))

    res = rigid_left_justify(par, width, space_char=space_char, fill_char=fill_char)
    print('Left Justified:\n')
    max_len(res)
    print(res)

    res = rigid_right_justify(par, width, space_char=space_char, fill_char=fill_char)
    print('\nRight Justified:\n')
    max_len(res)
    print(res)

    res = rigid_center_justify(par, width, space_char=space_char, fill_char=fill_char)
    print('\nCenter Justified:\n')
    max_len(res)
    print(res)

    res = rigid_left_right_justify(par, width, space_char=space_char, fill_char=fill_char, bias='random')
    print('\nLeft-Right Justified:\n')
    max_len(res)
    print(res)

    print('Max Line Width: ', _max_len)


if __name__ == "__main__":
    main()