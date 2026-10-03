CC      ?= gcc
CFLAGS  ?= -std=c11 -Wall -Wextra -O2 -Icore/include -Isim
LDFLAGS ?= -lm

# The sims use the Open Dynamics Engine (ODE) for real rigid-body physics
# (gravity/drag/wind force, torque, ground contact) instead of a hand-rolled
# integrator - see sim/sim_world.c. Needs the `ode-devel` (Fedora/RHEL) or
# `libode-dev` (Debian/Ubuntu) package. Prefer pkg-config; fall back to a
# plain -lode if this ODE build didn't install a .pc file.
ODE_CFLAGS := $(shell pkg-config --cflags ode 2>/dev/null)
ODE_LIBS   := $(shell pkg-config --libs ode 2>/dev/null || echo -lode)

BUILD   := build
CORE_SRCS := $(wildcard core/src/*.c)
SIM_COMMON_SRCS := sim/sim_world.c

.PHONY: all clean run-mother run-child test

all: $(BUILD)/mother_sim $(BUILD)/child_sim

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/mother_sim: sim/mother_sim.c $(SIM_COMMON_SRCS) $(CORE_SRCS) | $(BUILD)
	$(CC) $(CFLAGS) $(ODE_CFLAGS) -o $@ $^ $(LDFLAGS) $(ODE_LIBS)

$(BUILD)/child_sim: sim/child_sim.c $(SIM_COMMON_SRCS) $(CORE_SRCS) | $(BUILD)
	$(CC) $(CFLAGS) $(ODE_CFLAGS) -o $@ $^ $(LDFLAGS) $(ODE_LIBS)

run-mother: $(BUILD)/mother_sim
	./$(BUILD)/mother_sim

run-child: $(BUILD)/child_sim
	./$(BUILD)/child_sim

$(BUILD)/test_core: core/test/test_core.c $(CORE_SRCS) | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test: $(BUILD)/test_core
	./$(BUILD)/test_core

clean:
	rm -rf $(BUILD)
