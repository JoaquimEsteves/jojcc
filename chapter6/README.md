# Chapter 6: If statements and conditional expressions!

## TIL

> The order in which a program executes statements is its control flow, and the
> language constructs that let you change a program’s control flow are called
> control structures.

## Labels yo

Labels are a type of statement, so the following:

```c
if (0)
  foo:
    return 5
return 0
```

Will return 0!

This is the same as:

```c
if (0) {foo: return 5;}
return 0;

```
