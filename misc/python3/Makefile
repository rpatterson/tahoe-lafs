# Python 3 porting targets
#
# NOTE: this Makefile requires GNU make

### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL := bash
.ONESHELL:
.SHELLFLAGS := -xeu -o pipefail -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules


# Top-level, phony targets

.PHONY: default
default:
	@echo "no default target"

.PHONY: test-py3-all-before
## Log the output of running all tests under Python 3 before changes
test-py3-all-before:
	rm -f ../../.tox/make-test-py3-all-old.log
	$(MAKE) ../../.tox/make-test-py3-all-old.log
.PHONY: test-py3-all-diff
## Compare the output of running all tests under Python 3 after changes
test-py3-all-diff:
	rm -f ../../.tox/make-test-py3-all-new.log ../../.tox/make-test-py3-all.diff
	$(MAKE) ../../.tox/make-test-py3-all.diff
.PHONY: test-py3-all-swap
## Swap the new test output to the old, before log to compare the next set of changes
test-py3-all-swap:
	mv ../../.tox/make-test-py3-all-new.log ../../.tox/make-test-py3-all-old.log


# Real targets

# Gauge the impact of changes on Python 3 compatibility
# Compare the output from running all tests under Python 3 before and after changes.
# Before changes:
# `$ rm -f .tox/make-test-py3-all-*.log && make .tox/make-test-py3-all-old.log`
# After changes:
# `$ make .tox/make-test-py3-all.diff`
$(foreach side,old new,../../.tox/make-test-py3-all-$(side).log):
	cd "../../"
	tox --develop --notest -e py36-coverage
	(make VIRTUAL_ENV=./.tox/py36-coverage TEST_SUITE=allmydata \
		test-venv-coverage || true) |& \
		sed -E 's/^make\[[0-9]+\]: /make[#]: /' | \
		sed -E 's/([ =])0x[0-9a-z]{12}([ >])/\10x############\2/' | \
		sed -E 's/([ =])0x[0-9a-z]{12}([ >])/\10x############\2/' | \
		sed -E 's/ at [0-9a-z]{12}>/ at ############>/' | \
		sed -E 's/ at [0-9a-z]{12}>/ at ############>/' | \
		sed -E 's/\[(-?)[0-9]+\.[0-9]+s\]/[\1###.############s]/' | \
		sed -E 's/ in [0-9]+\.[0-9]{3}s$$/ in ###.###s/' | \
		sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}([T ])[0-9]{2}:[0-9]{2}:[0-9]{2}([.-])[0-9]{3}([0-9Z])/####-##-##\1##:##:##\2###\3/' | \
		sed -E 's/ Listener starting on [0-9]{,5}$$/ Listener starting on #####/' | \
		sed -E 's/ creating client 0: [a-z0-9]{4}$$/ creating client 0: ####/' | \
		sed -E 's/ \(TCP Port [0-9]{,5} Closed\)$$/ (TCP Port ##### Closed)/' | \
		sed -E 's/<Negotiation #([0-9]+) on [0-9]{,5}>/<Negotiation #\1 on #####}>/' | \
		sed -E "s/<<class 'twisted.internet.tcp.Port'> of <class '([^']+)'> on [0-9]{,5}>/<<class 'twisted.internet.tcp.Port'> of <class '\1'> on #####>/" | \
		sed -E "s/<<class 'twisted.internet.tcp.Client'> to \('([0-9.]+)', [0-9]{,5}\) at ############>/<<class 'twisted.internet.tcp.Client'> to ('\1', #####) at ############>/" | \
		sed -E 's/ creating client ([0-9]+): [a-z0-9]{4}/ creating client \1: ####/' | \
		sed -E 's/ with tub [0-9a-z]{32}>/ with tub ################################>/' | \
		sed -E 's/, _fd=[0-9]+,/, _fd=##,/' | \
		sed -E 's/priv-v[0-9]+-[0-9a-z]{52}/priv-v#-####################################################/' | \
		sed -E 's|/_trial_temp(-[0-9]+\|)/|/_trial_temp/|' | \
		sed -E 's|/test_mkdir([^/]*)/[^/]+/|/test_mkdir\1/########/|' | \
		tee "./misc/python3/$(@)"
../../.tox/make-test-py3-all.diff: ../../.tox/make-test-py3-all-new.log
	(diff -u "$(<:%-new.log=%-old.log)" "$(<)" || true) | tee "$(@)"

# Locate modules that are candidates for naively converting `unicode` -> `str`.
# List all Python source files that reference `unicode` but don't reference `str`
../../.tox/py3-unicode-no-str.ls:
	cd "../../"
	find src -type f -iname '*.py' -exec grep -l -E '\Wunicode\W' '{}' ';' | \
		xargs grep -L '\Wstr\W' | xargs ls -ld | tee "./misc/python3/$(@)"
