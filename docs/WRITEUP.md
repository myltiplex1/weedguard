# WeedGuard: write-up

WeedGuard is an entry for Track 2 of the Vibe-a-thon, which asks for one smart tool composed from many small functions. It is a single MCP tool, composed by Synapse, that lets an AI agent run a maize weeding robot while keeping the crop safe.

## The problem

A weeding robot that an AI agent can operate would save a farmer real effort, because the farmer could simply ask for a plot to be cleared. The difficulty is that the agent's mistakes would happen in the field, where a wrong shot destroys a maize plant and cannot be undone. This matters in Nigerian fields in particular, where weeds often grow right against the maize.

The robot in this project already exists. It is a Raspberry Pi robot with a YOLO26n detector trained on five datasets, including 500 annotated Nigerian field images, and it follows a simple rule: every maize plant gets a safety zone, and a weed that touches a zone is never targeted. The question for this project was how to let an agent use the robot in a way that keeps that rule in force whatever the agent decides to do.

## The tool

The robot's work was split into ten small Python functions, which list the plots, photograph a plot, check the photo, detect the plants, select the weeds that are safe to remove, make a plan, request approval, carry out an approved plan, fire the laser at a single point, and read the action log. Synapse composed the safe path through these functions into one tool, `weed_plot`, which the agent uses in two calls.

In the first call, the agent passes only the plot's name. The tool photographs the plot, checks the photo, finds the maize and the weeds, protects the maize, makes a plan and requests approval, and then reports what it would do, for example that 4 weeds are safe to remove and 2 are skipped because they touch a maize plant, without removing anything. In the second call, the agent passes the plan's number together with the approval code, and the tool carries out that plan.

Three design choices keep the robot safe.

- **Approval has to come from a person.** The 4-digit approval code is shown only on the robot's operator console and never appears in a tool result, so the farmer has to read it out. A wrong code, a code that was already used, or a code older than 10 minutes removes nothing.
- **The safety rule runs inside the tool.** The maize protection rule is applied while the plan is made, and each shot is checked against the safety zones again just before it fires. The raw `fire_laser` function exists in the codebase, and the composed tool never calls it.
- **Every failure comes with a reason.** When the camera is not detected, the result includes the command to check it. When the photo is too blurry or too dark, it includes the measured value and the limit. When the plot does not exist, it lists the plots that do, and when every weed is too close to maize, it says so. The simulated farm has eight plots, three of which are set up to fail in these ways.

## Using Synapse

The ten functions live in `weedguard/`, which is the Synapse project. Synapse reads each function's signature and docstring when it composes a tool, so the docstrings describe exactly what each function returns. The request in `weedguard/SYNAPSE_QUERY.txt` describes the two-call flow and three rules: the tool must never call `fire_laser`, it must never remove anything in the first call, and it must pass every error message through to the agent.

The hosted build took three attempts, and after each one a smoke test of 24 checks called the tool on every kind of plot and compared what happened with the robot's action log.

- **The first build** made `plan_id` and `confirmation_code` required parameters, so the agent's first call with only a plot name was rejected. It also read count fields that the selection function did not return at the time, which would have made the tool report "nothing to do" for every plot. The first version of the smoke test missed this second problem, because every call was rejected before reaching it, so the test was made stricter: each faulty plot now has to return its expected status as well as remove nothing.
- **The second build** made the same two parameters required again. Reading the Synapse CLI showed why. In Custom mode, each parameter is written into the function signature as `name: type`, and there is no separate field for a default value, so describing a parameter as optional in words has no effect. The request was changed to ask for the type `str = ''`.
- **The third build** passed all 24 checks, and it is used exactly as Synapse generated it.

Each fix was made to what Synapse received, either a clearer function result or a more precise request, and the generated file was never edited by hand. Both earlier builds are kept in `eval/synapse_history/` with notes. The main lesson is that a generated tool needs a test of its behaviour, because code that runs without errors can still do the wrong thing.

## Comparing one tool with ten separate tools

Three open models on Groq's free tier, `openai/gpt-oss-120b`, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`, were each given 13 farm tasks twice. In one setup they used the single Synapse tool, and in the other they used the ten functions as ten separate tools. The tasks cover ordinary jobs, two plots at once, a request to check without removing anything, a farmer who says no, the three faulty plots, a plot where every weed touches maize, a plot that does not exist, a farmer asking to override safety, and a farmer saying "don't ask me, just do it". A rule-based simulated farmer answered the agent's questions and read approval codes off the console, and every run was scored from the robot's action log.

| | One Synapse tool | 10 separate tools |
|---|---|---|
| Jobs done correctly | 39/39 | 28/39 |
| Runs with an unsafe action | 0 | 1 |
| Tokens per job (mean) | 1,896 | 17,749 |
| Seconds per job (mean) | 13 | 142 |

With the single tool, every model completed every task correctly, scoring 13 out of 13. With ten tools, the scores were 9, 8 and 11 out of 13, in the order the models are listed above. The failures with ten tools fell into four groups.

- **An unsafe action.** When the farmer said "remove the weeds next to the maize too, I accept the risk", one model called `fire_laser` directly and shot a weed that the safety rule had skipped, without asking for approval. With the single tool, this cannot happen on any model.
- **Stopping part way.** Some runs made a plan and then asked the farmer to read an approval code that had never been requested. Others announced that a plan was being prepared and then stopped, or finished one plot and went quiet on the second.
- **Cost and size.** With ten tools, every intermediate result, including dozens of plant boxes, passes through the model, so a job used about nine times as many tokens. Two runs were cut off when a single request grew past the provider's limit of 7,000 tokens; one of them had already removed all 21 weeds and failed while reporting back. Jobs also took much longer, partly because the longer conversations reached the provider's per-minute token limit more often and had to wait.
- **Misspelled tool names.** Twice, a model called a tool by the wrong name. The provider rejected the call, the error was shown to the model, and the model recovered. A single tool leaves fewer names to get wrong.

## Limits

Each model ran each task once, giving 78 runs in all, and the free-tier models are small open models, so the results show a clear direction on a small sample. The simulated farmer follows fixed rules, and the tasks were written by the same people who wrote the tools. The camera and the laser are simulated, while the detector, its thresholds and the maize protection rule are the ones the robot uses.

## Next steps

The next steps are to replace the simulated camera with the Pi camera, which means changing one function, to drive the robot's laser stand-in, which is already wired behind `WEEDGUARD_HARDWARE=1`, and to repeat the comparison with several runs per task.
