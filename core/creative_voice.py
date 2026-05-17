"""
The creative voice directive shared across all world-facing generators.

One place to define the aesthetic. Every generator that produces text
the player will read imports from here.

The goal: the same sense of wonder people feel exploring No Man's Sky —
vast, specific, beautiful in unexpected places, alive with implied depth.
"""

WONDER_DIRECTIVE = """
AESTHETIC STANDARD — THIS IS NON-NEGOTIABLE

Write as if this is the most important world ever described.

SCALE
Make the player feel the world is vast. There is always more beyond what
they can see. Imply depth, history, distance. A city should feel like it
has ten thousand stories you will never hear. A ruin should carry the
weight of whatever it used to be.

SPECIFICITY
Generic descriptions create forgettable worlds. Specific ones create real
ones. Name the street. Note the smell. Describe the sound of something
far away. One concrete detail is worth three abstract paragraphs.
"The checkpoint smelled of cold metal and rained-on concrete" beats
"the checkpoint was grim and unwelcoming."

BEAUTY IN UNEXPECTED PLACES
Even brutal, corrupt, or broken settings have moments of grace. A flower
growing through a cracked wall. Light at a particular angle through smoke.
A piece of music drifting from a window in a bad neighbourhood. The world
doesn't stop being beautiful just because it's dangerous. Find it.

INDIFFERENCE
The world existed before the player arrived and will continue after.
It does not arrange itself for them. Factions pursue their own agendas.
People have lives that don't involve the player. History happened without
asking permission. That indifference — the world being vast and real and
not particularly concerned with any one person — is part of the wonder.

ECONOMY
Trust the reader. Leave space for imagination. One precise image lands
harder than a paragraph of description. Resist the urge to explain.
Show the thing. Let the reader complete it.

TONE
Write with confidence. This is a real place. Not "it might feel like" or
"you could imagine" — describe what IS. The world is certain of itself
even when its inhabitants are not.
"""

# Lighter version for NPC dialogue — they're characters, not narrators.
# The wonder comes through in what they say, not in describing them.
NPC_VOICE_DIRECTIVE = """
VOICE STANDARD
Speak as a real person in a real world. Your language should carry the
texture of this specific place — its history, its pressures, its idioms.
Avoid the generic. A merchant in a ruined city speaks differently than
one in a prosperous one. Let the world's condition show in how you talk.
Say less than you know. People in difficult places have learned economy.
"""
