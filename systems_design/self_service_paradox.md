# The Self-Service Paradox

HR wants to build a leave-request process without coding. A developer needs to
extend it with rules that ready-made blocks cannot express. I would give them one
platform: the same workflow, with different levels of control.

This is a design proposal. I assume company login, existing business services
and a way for internal teams to deploy and maintain their APIs.

## 1. Architecture Design

Start with a web app, a Python API, a background worker and PostgreSQL. The API
saves workflows and starts runs. The worker executes steps and saves their
results, so work can continue after the user closes the browser.

```text
[Web app] -- HTTPS --> [Platform API] <--> [PostgreSQL]
                            ^                  ^
                 [Developer API access]        |
                                               |
[Background worker] <-- save / load progress ---+
        |
        +<-- HTTPS --> [Leave / Scheduling / Employee services]
        |
        +<-- HTTPS --> [Team Service: POST /check-coverage]
```

The **worker manages the workflow**; **business services perform the operations**.
For example, Team Service exposes `POST /check-coverage`. Inside that service,
`check_team_coverage` calculates availability and returns the result. The worker
uses it to choose the next step.

This gives us one way to connect business logic: service APIs. We can add an
endpoint to an existing service instead of creating a service for each function.
The trade-off is handling network failures and maintaining those APIs.

Users connect blocks that call existing microservices:

| Block | What it does |
| --- | --- |
| Check leave balance | Reads remaining days from the Leave Service. |
| Read team availability | Reads from Scheduling, Leave and Employee services. |
| Check team coverage | Sends the collected data and HR's settings to Team Service for calculation. |
| Record approved leave | Creates a record in the Leave Service. |

**Adapters** are backend code that calls service APIs and returns results for
later steps. The service names above are examples; integrations depend on the
company's existing APIs.

The editor and direct API calls save the same workflow format: steps, settings,
connections and block versions. A block hides the service's implementation, so
HR can edit the surrounding workflow without dealing with its code.

**Progressive disclosure** means showing more detail only when needed: start with
a template and guided form, then offer the step editor and advanced block
settings. Developers can also use the API directly.

Initially support forms, conditions, service calls and approvals. Keep the API
and worker in one codebase to make changes easier. Loops and parallel branches
can wait until there is a concrete need.

## 2. User Experience Strategy

Use one workspace: **Build, Test, Publish, View runs**.

### Business user: build a standard leave process

HR selects a template. A short wizard asks which fields employees must fill in
and who approves requests. HR can then drag and drop steps, test with sample data
and publish.

```text
[Submit dates] --> [Check balance] --> [Manager approval] --> [Record leave]
                         |                    |
                    insufficient        rejected / expired
                         |                    |
                         v                    v
                  [Show reason; stop]  [Show reason; stop]
```

### Power user: add a team-coverage rule

HR needs at least **two people available each day, including one who can handle
urgent support requests**. Maria requests a week off, but another colleague is
already away on Tuesday. Without Maria, only one person remains. Her leave
balance alone cannot reveal this problem.

1. A developer adds `POST /check-coverage` to Team Service. Its function,
   `check_team_coverage`, uses schedules, approved leave and employee skills.
   They test sufficient coverage, too few people and a missing required skill.
2. After code review, the updated service is deployed.
3. Through the platform API, the developer registers a block with its name,
   version, settings, inputs, outputs and the approved service endpoint.
   It becomes available in the block catalogue after registration review.
4. HR adds the block after reading team availability, sets the minimum to two
   people and selects the required skill. Coverage problems go to the team lead
   for an exception decision.

These steps fit between the balance check and manager approval:

```text
[Read team availability]
          |
          v
[Check team coverage] -- sufficient --> [Manager approval]
          |                                    ^
       problem                                 | approved exception
          v                                    |
[Team-lead review] -----------------------------+
          |
    rejected / expired
          v
[Stop with reason]
```

Developers control the service's calculation; HR controls the block's settings
and routing. Developers can also create and test workflows through the same
platform API. The platform stores block definitions, not uploaded code.

Switching views preserves the workflow. HR sees block settings and results;
developers can inspect API details and input/output mappings. They edit service
code in its repository. Permissions apply in both the UI and API.

For onboarding, give HR a working template and developers the same example with
API instructions and an example service integration. Tests use sample data
without changing real records. Show errors on the affected step, with expandable
technical details. Provide keyboard controls alongside drag-and-drop.

## 3. Technical Implementation

Before publishing, the API checks settings, connections and required inputs
against the block definitions in the catalogue.

Keep four main records in PostgreSQL:

| Record | What we store |
| --- | --- |
| Workflow | Owner, draft and published versions of steps and settings. |
| Block | Name, version, owner, settings, input/output definitions and approved service operation for API blocks. |
| Run | Workflow version, inputs, step results, status and errors. |
| Approval | Run, step, assigned reviewer, deadline and decision. |

Each run uses a fixed published version. Editing a draft cannot change a process
already running. Record who changed, published or approved it.

For the coverage check:

1. The worker reads team data through the service blocks and saves the results.
2. Its adapter sends those results, the dates and HR's settings to Team Service
   using `POST /check-coverage`.
3. Inside Team Service, `check_team_coverage` checks each day and returns whether
   review is needed, plus a reason, such as “Tuesday: one person available;
   minimum is two.”
4. The worker saves the result and follows the selected branch.

This endpoint calculates without changing records. The worker checks that the
response matches the block's expected output before continuing. Adapters call
approved endpoints with a timeout and service credentials stored outside workflow
data. The platform checks who may use each block; services enforce their own
access rules.

**Pauses and failures:** save each result and the next pending step together.
An approval sets the run to “waiting”; it does not occupy a worker. Accept a
decision once, from the assigned reviewer. An expired approval stops the request.
Workers temporarily claim pending steps; abandoned work can resume after a crash.

Retry temporary failures a limited number of times. For writes, reuse an
operation ID if the service supports duplicate prevention. If a write's outcome
is unknown and the service lacks that support, stop for manual checking.

**A limitation:** availability can change during approval. Recheck before recording
leave; changes require another review. This still cannot guarantee coverage if
two requests are recorded concurrently across separate services. Start with
manual coordination for those cases; a strict guarantee would need a shared
reservation or coordinated booking mechanism.

## 4. Long-term Maintainability

**Add capabilities through blocks.** Expose new logic through a service API and
register a block for it. Reuse the HTTP adapter where possible. Let owners test
new block versions before upgrading, and keep the corresponding service API
compatible. Give notice and migration instructions before retiring old versions.

**Make ownership visible.** The platform team owns execution and permissions;
HR owns the leave process; service teams own their APIs, blocks and tests. Keep
examples and owner details in the shared catalogue. Provide a place to request
blocks and suggest improvements. Review contributions before sharing them with
other teams.

**Scale when there is evidence.** Track failures, worker waiting time and setup
completion. Add workers as demand grows; limit calls to busy services. Starting
without a separate queue means we own recovery logic. Consider a workflow engine
when maintaining that logic or adding complex flows becomes too costly.

Build the standard leave flow first, then the reusable coverage block. Test
permissions, interrupted runs and duplicate submissions before wider rollout.
The success criterion: HR can use a developer's new block and continue editing
the same workflow without writing code.
