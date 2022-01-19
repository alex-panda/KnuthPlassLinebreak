flags = -Wall -g
outfilename = knuth_plass

run_all:
	echo "No "


knuth_plass_filename = knuth_plass.cpp
knuth_plass_out = knuth_plass.exe

run_knuth_plass: build_knuth_plass
	@$(knuth_plass_out)

build_knuth_plass:
	g++ $(flags) $(knuth_plass_filename) -o $(knuth_plass_out)
