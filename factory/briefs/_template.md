# <nnn> <One-line title>
Agent: <kebab-case-name>
Role: <one line for the agents/AGENTS.md registry table>
Purpose: <what the agent does and for whom>
Inputs: <what the user, files or APIs provide>
Outputs: <what it returns or stores>
Permissions: <what it may read, write, call; what it must never do>
Side effects: <external effects; "none" if none>
Offline behavior: <what works with no provider key>
Memory: <records, where they live (agent data dir), how long they are kept>
Surfaces: <any of: cli, tools, api, ui>
Subagents: <none, or each one's single job>
Out of scope: <what must not be built>
Verification: bash factory/check.sh <kebab-case-name>
