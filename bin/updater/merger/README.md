# IX stable merger

`updater_merger run` promotes a pinned `pg83/ix:main` revision to
`stal-ix/ix:main` after `./ix build set/ci/tier/0 --seed=1` succeeds through
Molot. It builds the actual merge tree, including any changes already on
stable. The command runs once per 86400 seconds through the cluster scheduler,
dedup and `/lock/updater/merger/work`; updater and fixer remain independent.

Publication preserves the existing `stable` PR / merge-commit history. A
snapshot branch `pg83:merger/stable-<source SHA>` pins the PR input while dev
continues moving. The merge's first parent is the previous stable revision,
its second parent is the pinned source. Both author and committer are
`SCP-2603 <351190792+scp-2603[bot]@users.noreply.github.com>`.

The GitHub token is loaded from the local secret service only after the full
build succeeds. The worker pushes the local merge without force, rather than
using GitHub's merge endpoint (which would use the token owner's identity).
GitHub marks the corresponding PR merged when that commit reaches its base.
Snapshot branches are retained as references to the checked source revisions.

If stable moves before publication, build a new merge against the new base.
Never rebase a green merge or include a newer dev head without building it.
Push failures retry up to ten times, fifteen seconds apart. Build failures,
merge conflicts, or changed tracked build inputs stop the run without moving
stable. If the pinned source is already in stable, there is nothing to do.

Logs are stored under the gorn root `updater_merger` for seven days. The PR
and merge message retain the build command and built tree hash.

Optional endpoint overrides for isolated runs: `IX_MERGER_MIRROR_URL`,
`IX_MERGER_SOURCE_URL`, `IX_MERGER_TARGET_URL`, `IX_MERGER_TOKEN_URL`.
