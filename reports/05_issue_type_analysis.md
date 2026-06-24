# Issue Type Analysis

- Total issue types: 133
- Global (shared): 60
- Project-scoped: 73
- Standard types: 110
- Sub-task types: 23

## Hierarchy Levels

| Level | Count | Types |
|---|---|---|
| -1 | 23 | Design Sub-task, Dive Sub-task, Sub Test Execution, Sub-Task, Sub-Test, Sub-task, Subtask |
| 0 | 97 | Ask a question, Asset, Bug, Change, Change Request, Code Freeze Override, Company Risk Acceptance Request, Compliance, Corrective Action, DR System Request, Deploy Equipment Request, Design Story, Dive, Emailed request, Enablement Task, Evidence Request, Feature, General request, Idea, Improvement, Incident, Initiative, Insight, Key Initiatives, Novel, PM Task, Phase, Portfolio, Precondition, Problem, Program, Project, Replace Equipment Request, Request AWS Product, Research, Research/Spike, Return Equipment Request, Risk Treatment Request, Service Request, Service Request with 1-Step Approval, Service Request with 2-Step Approval, Service Request with 3-Step (1-Approval) Approval, Service Request with 3-Step (2-Approval) Approval, Service Request with 4-Step Approval, Service Request with optional approval step, Simple Approval Request, Story, Submit a request or incident, Task, Technical Story, Tenable Vulnerability, Tenable Vulnerability Host, Test, Test Case, Test Execution, Test Plan, Test Set, [System] Change, [System] Incident, [System] Post-incident review, [System] Problem, [System] Service request, [System] Service request with approvals, test |
| 1 | 12 | Epic, New Campaign Creation, Planning, Risk |
| 2 | 1 | Initiative |

## Duplicate Issue Type Names

| Name | Occurrences | Global? | Project-Scoped IDs |
|---|---|---|---|
| Task | 18 | Yes | 15668, 15698, 16310, 17774, 17808, 15666, 15674, 15673, 15696, 15701, 15699, 15700, 15680, 15711, 15713, 15702, 19042 |
| Sub-task | 16 | No | 17808, 15700, 15673, 15701, 15883, 19042, 15699, 15702, 15666, 15713, 15674, 15680, 15711, 15668, 15696, 17774 |
| Epic | 9 | Yes | 17774, 15680, 15698, 15711, 16310, 15702, 19042, 17808 |
| Story | 7 | Yes | 17774, 17808, 19042, 15680, 15711, 15702 |
| Idea | 7 | No | 17975, 15654, 15614, 17740, 19043, 17707, 17808 |
| Bug | 4 | Yes | 15680, 15711, 15702 |
| Subtask | 2 | No | 15698, 16310 |
| Research | 2 | No | 15673, 15680 |
| Initiative | 2 | Yes | 16079 |

## Align-Required Issue Types

Jira Align expects these hierarchy types to map correctly:

| Align Level | Align Name | Jira Equivalent | Present? |
|---|---|---|---|
| — | Epic | Epic | Yes (1) |
| — | Story | Story | Yes (1) |
| — | Task | Task | Yes (1) |
| — | Bug | Bug | Yes (1) |
| — | Sub-task | — | **MISSING** |
| — | Initiative | Initiative | Yes (1) |

## Non-Standard Issue Types (review for Align compatibility)

| Name | Scope | Description |
|---|---|---|
| Design Sub-task | Global | A sub-task of the issue used for design/UX work. (Migrated on 10 Dec 2024 03:13  |
| Sub-Test | Global |  |
| Sub Test Execution | Global | This is the Xray Sub Test Execution Issue Type. Used to execute test cases alrea |
| Dive Sub-task | Global | A sub-task of the issue used for diving (Migrated on 10 Dec 2024 03:13 UTC) |
| Test Case | Global |  |
| Test | Global | This is the Xray Test Issue Type. Used to define test cases of different types t |
| Test Execution | Global | This is the Xray Test Execution Issue Type. Used to execute test cases already d |
| Novel | Global | Novels consist of a group of sub-tasks that relate to a feature/enhancement or t |
| PM Task | Global | (Migrated on 10 Dec 2024 03:13 UTC) |
| Service Request with optional approval step | Global |  |
| Ask a question | Global | Have a question? Submit it here. |
| DR System Request | Global |  |
| Code Freeze Override | Global |  |
| General request | Global | For general requests |
| Tenable Vulnerability | Global | Tenable Managed Vulnerability Issue Type |
| Request AWS Product | Global |  |
| [System] Post-incident review | Global | Document and share incident learning. |
| Evidence Request | Global | Controls Compliance: Evidence Request from LogicGate |
| Corrective Action | Global | Controls Compliance: Corrective Action from LogicGate |
| Risk Treatment Request | Global | Cyber RM: Risk Treatment Request from LogicGate |
| Dive | Global | Dives are time-boxed stories to determine, how much work is needed, possible ETA |
| Technical Story | Global | These stories are based around development work that is non-feature or enhanceme |
| Incident | Global | For system outages or incidents. Created by Jira Service Desk. |
| Change | Global | For system upgrades or alterations. Created by JIRA Service Desk. |
| Research/Spike | Global | Task centered around research on a question about applications or data.  |
| Submit a request or incident | Global | Submit a request or report a problem. |
| Service Request with 1-Step Approval | Global | Requests that may require 1 approval step |
| Service Request | Global | A request that follows ITSM workflows. |
| Problem | Global | Track underlying causes of incidents. Created by Jira Service Desk. |
| Emailed request | Global | Request received from your email support channel. |
| [System] Service request | Global | A request that follows ITSM workflows. |
| [System] Service request with approvals | Global | A request that follows ITSM workflows. |
| [System] Change | Global | Created by Jira Service Desk. |
| [System] Problem | Global | Track underlying causes of incidents. Created by Jira Service Desk. |
| [System] Incident | Global | For system outages or incidents. Created by Jira Service Desk. |
| Asset | Global | A digital or physical item to be tracked. |
| Improvement | Global | An improvement or enhancement to an existing feature or task. (Migrated on 10 De |
| Design Story | Global | (Migrated on 10 Dec 2024 03:13 UTC) |
| Compliance | Global | (Migrated on 10 Dec 2024 03:13 UTC) |
| Tenable Vulnerability Host | Global | Tenable Managed Vulnerability Host Issue Type |
| Service Request with 3-Step (1-Approval) Approval | Global | Requests that may require up to 3 approval steps, with all steps requiring only  |
| Service Request with 3-Step (2-Approval) Approval | Global | Requests that may require up to 3 approval steps, with the 1st step requiring 2  |
| Service Request with 2-Step Approval | Global | Requests that may require 2 approval steps. |
| Deploy Equipment Request | Global |  |
| Return Equipment Request | Global |  |
| Service Request with 4-Step Approval | Global |  |
| Replace Equipment Request | Global |  |
| Simple Approval Request | Global |  |
| Company Risk Acceptance Request | Global |  |
| Precondition | Global | This is the Xray Precondition Issue Type. Used to abstract common actions that m |
| Test Set | Global | This is the Xray Test Set Issue Type. Creates a group of test cases. Used to ass |
| Test Plan | Global | This is the Xray Test Plan Issue Type. Used to define the scope of test cases fo |
| Risk | Global |  |
| Planning | Global |  |
| Initiative | Global |  |
