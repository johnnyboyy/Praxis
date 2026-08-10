# praxis root: skills-house

# This file is the root marker `root_tree` discovers. Plugins moved in with plugin_import
# land beside it (engine/plugins, handoff/plugins, phases, scripts); chunks/ and handoffs/
# are created by the ledger and handoff primitives on first write.
#
# debug: yes → closing a ratified handoff archives it under handoffs/archive/ instead of
# deleting it (handoff.py). Default off.
debug: yes

# engine-plugins → where this root's judgment engine is registered, so frame/route
# auto-resolve it without --engine-plugins passed by hand. This repo is self-hosting: its own praxis/
# is the pristine core (empty slot), so the engine (corpora) is registered in its plugin contribution
# rather than imported into the core slot. Path is relative to this root.
engine-plugins: corpora/praxis-plugin/engine/plugins
