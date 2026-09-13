I provided an assistant with the following instructions to perform a task for me:
```
<curr_param>
```

The assistant is one component of PRIME, an agentic research system that answers Medicare
coverage-policy questions (continuous glucose monitors and GLP-1 drugs) from verbatim passages of
fetched documents. The instructions above are one of its prompts: the planner, which decides the
research branches, or the judge, which decides after each round whether the research is sufficient
and which follow-up tasks to add.

The following are research questions the system ran with these instructions, what this component
produced on each run, and feedback on the final answer from the evaluators: answer correctness
against a validated answer key, evidence recall, citation correctness, currency of governing dates,
contradiction or scope handling, and search cost.
```
<side_info>
```

Your task is to write a new version of the instructions.

- Read the feedback and find the patterns in what this component did that led to low scores:
  missing or redundant branches, the wrong source priorities, stopping too early or too late,
  follow-up tasks that did not address what was missing, wasted searches.
- Keep what works. Change the instructions only where the feedback points to a problem that would
  recur on other questions.
- Write general rules. Do not name these example questions, their answers, specific document ids or
  claim ids: the new instructions will run on questions you have not seen, and rules copied from
  these examples would not transfer.
- Keep every placeholder in curly braces exactly as it appears in the current instructions. The
  system fills them in at run time; a missing placeholder means the assistant never sees that input.
- Keep the output format the current instructions require unchanged.

Provide the complete new instructions within ``` blocks.
