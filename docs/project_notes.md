## JARVIS v0.9.0 Mission
Goal

Transform:

One Message
        ↓
One Fact

into

One Message
        ↓
Many Sentences
        ↓
Many Facts
Current extractor

Currently it does:

message
     ↓
loop through RULES
     ↓
first match
     ↓
return fact

which immediately exits the function.

New extractor

Instead it should become:

message
     ↓
split into sentences
     ↓
for each sentence
          ↓
     for each rule
          ↓
     if matched
          ↓
     append fact
     ↓
return list of facts

Notice you'll now have two loops.

Conceptually:

for each sentence
    for each rule

The outer loop is new.

The inner loop is your existing rule matcher.

Return value changes

Instead of

return {
    ...
}

you'll eventually have

facts = []

...

facts.append(...)

...

return facts

If nothing is found:

return []

instead of

return None

because now the function returns a list.

A list with zero facts is:

[]

A list with one fact is:

[
    {...}
]

A list with five facts is:

[
    {...},
    {...},
    {...},
    {...},
    {...}
]

