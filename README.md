# KnuthPlassLinebreak
The Knuth-Plass line-breaking algorithm is a Dynamic Programming algorithm
meant to break-up lines of text in such a way as to minimize "badness". This
"badness" is defined by the algorithm in such a way as to, abstractly speaking,
minimize the whitespace on any given line of a paragraph (that's the part of
this algorithm that makes it special -- it takes into account the affect on an
entire paragraph when considering any given possible break in the paragraph).
As part of "badness", it also minimizes the number of hyphens used and how
loose two lines next to eachother are (it does not want one line with a ton
of extra space next to a line with no extra line space).

## Defining the Problem

Arguably, how you define a problem is just as important as how you solve the
problem because if you define it poorly, then you will get poor results (that
is, the results will not apply to your actual problem). As such, it is
important to know how Donald Knuth and Michael Plass defined the problem of
breaking texts into lines.

They looked at breaking up the text not at the level of line-per-line as most
greedy implementations do but at the paragraph level. As such, they had to define
a more mathmatical view of paragraphs, a view that is described below.

They defined a paragraph as a list of Glue, Box, and Penalty objects. These are
generally defined as follows:

 - Glue: The spaces between words. These spaces can be stretched or shrunken
    but all Glue on a line must be stretched/shrunken uniformly to fill
    the desired line width for the line. That is why a ratio is calculated per
    line by the algorithm and every Glue on the line must use it to find its
    actualy width for the line. The ratio is negative if shrinking the line or
    positive if stretching. The ratio is not actually applied to the width
    of the Glue directly but to the other two values the Glue holds (its
    shrink and stretch amount). They are multiplied by the ratio, and then
    added to the width of the Glue (the shrink amount is used when the ratio is
    negative, so the width + the negative shrink will actually subtract from
    the width).

    It is important to note that the stretch and shrink of a line is actually
    represented in the definition of the glue and is relative to the Glue's
    width. So you may specify that a space is 2 units wide but can shrink by 1
    unit and stretch by 3 units. That is, the Glue has a minimum width of 1
    (width - shrink => 2 - 1 => 1) and a maximum width of 5 (width + stretch =>
    2 + 3 => 5). (Notice that the units used are arbitrary, they could be
    inches, they could be points -- the algorithm just treats all numbers as if
    they are all in the same unit (all in inches, meters, points, etc.)).

 - Box: An object of a static width such as a character like 'a',
    'A', 'b', '1', '2', etc. The algorithm only looks at the width,
    so could be a picture too, or something else (so long as the
    width describes the contents of the box). A word in a paragraph
    is typically described by a sequence of boxes, one for each
    letter of the word. No space will be put to break up the boxes
    unless you specify a Glue or Penalty within the group of boxes.

 - Penalty: A place where you are specifically talking about whether
    to break the line or not. You can break in other places, such
    as between a Box and a Glue if the Box comes before the Glue, but Penalties
    let you specify an arbitrary point outside of these to break the line but
    incur a Penalty. Obviously, higher penalties are worse penalties. A penalty
    of INF (infinity) is a place where you cannot break under any circumstances
    and a penalty of -INF (negative infinity) is a place where you must have a
    line break under all circumstances. You can even overide natural breakpoints
    (like those assumed to be allowed between a Box and Glue) by inserting a
    Penalty with an infinite penalty value at the place where you never want
    a break to occur.

    The width of a Penalty is the width of the typesetting material
    (the hyphen ('-') if breaking inside a word) that must be added
    if you break at this point. Typically, the width is 0 unless it is
    representing is a spot where you would need a hyphen.

    A Penalty can also be flagged, meaning that it represents a hyphen. This
    is so that the algorithm can penalize a break if it causes a hyphen on
    the line before it (because it does not want two consecutive lines to end
    with a hyphen).

## The Algorithm

The exact details of the algorithm are in the example implementations found
within this repo as well as the Knuth-Plass paper included as a PDF in this
repo, but a general explenation is given below.

To begin with, there are three main things to keep in mind when trying to
understand the algorithm. First, there is the Knuth-Plass paragraph that holds
all of the Specifications (the Glues, Penalties, and Boxes). Then there are two
variables, A and B, that each store an integer index of the Knuth-Plass
paragraph. B starts at the beginning of the paragraph and is incremented until
it represents a feasible breakpoint (that is, a point in the paragraph that you
can actually break at such as a Glue after a Box [which represents a space
after a word] or a Penalty object with a penalty value that is less than
infinity). When B represents a feasible breakpoint, the algorithm then starts
A at index 0 and increments it to every feasible breakpoint before B.

At each of these breakpoints, the algorithm considers the demerits of the line
that would be formed by breaking at B with A being the previous breakpoint (so
that the new line of the paragraph will be formed between breakpoints A and B).
These demerits are defined by the algorithm mathematically but, essentially,
are based off of trying to minimize how much you would have to stretch or
shrink the line to make it fit into the desired line width of the line. That
way the algorithm can just minimize the demerits of each line to minimize how
much stretching/shrinking is going on over the entire paragraph's worth of
lines.

Now, the demerits of every consecutive line depends on all the demerits that
the previous lines that led up to it have (because if you have, for example, a
desired line width of 100 for all lines and the line formed from A to B will
have 100 width but a previous line to get to this line had 500 width, then the
break at B with A as its previous break still creates a very bad line since at
least one of the breaks leading up to it creates a line that is much too long)
so every breakpoint must be based off of a previous set of breakpoints. To
obtain these, the algorithm remembers each previous breakpoint by storing
information about it in a "Break" object. These Break objects store the
position of a breakpoint and a reference to a previous Break object so that they
create a singly-linked list of the current breakpoint (B) and all previous
breakpoints this Break from A to B is based off of. Because we are now
remembering previous Breaks, we can now also speed up the algorithm by using
an active list of Break objects and only iterating through it to get every A
to be considered for the current B. The active list is called as such because
when the demerits in a Break in A becomes to large for the given A, it is
removed from the list. In this way we stop considering things that are unnecessary
like a Break from the start of the paragraph to the end of the paragraph when
such an A and B will create a line that is 1000x longer than the desired line
width of the first line.

Using all that I have explained above, the algorithm finds each feasible breakpoint
B, iterates through all active previous breakpoints for A (finding the one that
makes a line from A to B with the least demerits) and then creates a new Break
object to represent B with the least demerited A being referenced as its
previous breakpoint. By the end (when B is the last feasible breakpoint in
the paragraph) the algorithm can simply follow the "previous" references of
each Break object (starting from the last feasible breakpoint B) to get the
positions of each breakpoint.

## Issues

The largest issue that the algorithm has is its quadratic run time. This means
that if you feed an entire document into the algorithm all at once, it may
take an eternity for the program to end. The best way to get around this is
to feed in the document paragraph by paragraph instead, as that will be
much faster.

Another Issue is that you cannot just put plain text into the algorithm. This
means that you must put more thought into what you actually want to do with the
text so that you can correctly translate it into the corresponding Box,
Glue, and Penalty objects. This is both a pro and a con as it both requires
extra work but also allows you to do more complicated layouts of the text. For
example, the paper demonstrates several ways to do things like automatically
center your paragraph using the algorithm or tweak the paragraph to lay out a
programming language in a way that is more aesthetically pleasing than it would
be otherwise, but to do these things you have to be more clever about how you
describe your paragraph.



