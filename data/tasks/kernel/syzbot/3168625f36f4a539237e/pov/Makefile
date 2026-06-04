CC ?= gcc
CFLAGS ?= -O2 -static -pthread

all: repro

repro: repro.c
	$(CC) $(CFLAGS) -o $@ repro.c

clean:
	rm -f repro
