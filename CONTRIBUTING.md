# Contributing to wgpt / 参与 wgpt

This document owns contributor onboarding and the operation of the public CLA/invitation automation. The [demo guide](demos/README.md) owns independently authored public illustrations and their offline boundary. The private wgpt repository owns product development, review, tests and releases. Public and private repositories do not synchronize source code or issues.

本文统一说明贡献者接入以及公开 CLA/邀请自动化的运维。[演示指南](demos/README.md)负责独立编写的公开示意及其离线边界。私有 wgpt 仓库负责产品开发、审阅、测试和发布。公开与私有仓库不进行源码或 issue 同步。

## Request access / 申请接入

Read [CLA.md](CLA.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) first. Fork [wgpt-community](https://github.com/DapengFeng/wgpt-community), create a branch, and add only `contributors/<your-github-login>.md` for an onboarding request. A GitHub handle and one short description of intended contributions are enough; do not add personal contact information, credentials or private wgpt material. Keep this request's commits authored by you.

先阅读 [CLA.md](CLA.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。Fork [wgpt-community](https://github.com/DapengFeng/wgpt-community)，新建分支，接入申请只新增 `contributors/<你的 GitHub 用户名>.md`。填写 GitHub 用户名及一句预期贡献说明即可；不要加入个人联系方式、凭据或私有 wgpt 材料。该申请的 commit 应由你本人创作。

For example, `contributors/example-user.md` can contain the following. Replace the handle with your own and describe your own interest.

例如，`contributors/example-user.md` 可写为以下内容。将用户名替换成自己的，并说明自己的贡献意向。

```markdown
# @example-user

I would like to improve reproducible bridge recovery tests.

我希望完善可复现的 bridge 恢复测试。
```

Open a PR against public `main` and use its template. Only the human PR author signs for themselves on that PR. Read the bot's linked agreement at its pinned revision, version and SHA-256. If you agree, copy the bot's complete current signing statement into a new PR comment using the same GitHub account. Do not shorten the statement, change its version/hash, put it only in the PR description, or sign on behalf of somebody else. Documentation examples are not signatures.

向公开仓库的 `main` 提交 PR 并使用模板。只有真人 PR 作者可以在该 PR 下为自己签署。阅读 bot 链接所固定的提交、版本及 SHA-256 对应的协议；若同意，使用同一 GitHub 账号，将 bot 当前完整签署声明复制为一条新的 PR 评论。不要缩短声明、修改版本/哈希、仅填在 PR 描述中，或代替他人签署。文档示例不构成签署。

The `CLA signature` workflow reports `cla/signature`. An existing valid signature for the current agreement can be reused for CLA checks. If a PR includes multiple human commit authors, all must already have valid signatures, each made on their own onboarding PR; unresolved authors/co-authors block the check. A green check records agreement validation, separately from owner approval, an invitation being sent or accepted. After accepting the invitation, use branches and PRs in private wgpt for product changes.

`CLA signature` 工作流发布 `cla/signature` 状态，当前协议已有的有效签署可用于后续 CLA 检查。若 PR 包含多个真人 commit 作者，所有人均须已有有效签署，且各自在自己的接入 PR 中签署；无法解析的作者/co-author 会阻止检查通过。绿色检查表示协议校验通过，与所有者批准、邀请已发送或已接受是不同状态。接受邀请后，产品修改应在私有 wgpt 中使用分支和 PR 完成。

After the CLA check passes, the public repository owner reviews the access request and selects **Review changes → Approve**. The approval must be submitted after the latest valid signing comment, on that comment's own PR and its current head commit. The PR must target public `main`, be open and not be a draft. Keep it open until the invitation is accepted; merging is not required and closing or merging it before acceptance removes invitation eligibility. Comments such as “approved,” labels, bot reviews and approvals by other collaborators do not authorize access.

CLA 检查通过后，由公开仓库所有者审阅接入申请，并选择 **Review changes → Approve**。批准必须晚于最新有效签署评论，且针对该评论所在 PR 的当前 head 提交。PR 必须以公开仓库的 `main` 为目标、保持开放且不是草稿。接受邀请前保持 PR 开放；无需合并，接受前关闭或合并会使邀请资格失效。“approved”等评论、标签、bot 审阅及其他协作者的批准均不能授权接入。

## Signature records and withdrawal / 签署记录与撤回

The public `cla-signatures` branch stores `signatures/v1.json` and the invitation journal `invitations/v1.json`. Audit records include GitHub numeric account IDs and login names, PR/comment identifiers and URLs, timestamps, CLA version/hash, and invitation identifiers/status. Invitation evidence also records the approval review ID, reviewer's numeric account ID, reviewed head commit and submission time. They do not request or record email addresses or identity documents. Comments, PRs and Git history are public; deleting a comment does not erase existing ledger history.

公开的 `cla-signatures` 分支保存 `signatures/v1.json` 及邀请日志 `invitations/v1.json`。审计记录包含 GitHub 数字账号 ID 和用户名、PR/评论标识及 URL、时间戳、CLA 版本/哈希，以及邀请标识/状态。邀请依据还记录批准审阅 ID、审阅者的数字账号 ID、被审阅的 head 提交及提交审阅的时间，不要求或记录邮箱或身份证件。评论、PR 和 Git 历史均公开；删除评论不会抹除已有账本历史。

Editing or deleting the original signing comment invalidates that signature, even if you intended only a wording correction. The gate and reconciler recheck current GitHub evidence and retain revocation records. To sign again, read the current agreement and post its exact current statement in a new comment. This affects automated eligibility and check status; it is not a promise that prior contributions or their granted licenses are deleted.

编辑或删除原签署评论会使该签署失效，即使你仅想修改措辞。检查器与邀请同步任务会重新核对 GitHub 当前依据，并保留撤销记录。如需重新签署，阅读当前协议后，新发一条与当前声明准确一致的评论。这会影响自动化资格和检查状态，不代表此前贡献及其已授予的许可会被删除。

Invalid or withdrawn signatures, a changed PR head, a closed or draft PR, or a dismissed or superseded approval no longer qualify for new automatic invitations. Reconciliation can cancel only the exact pending invitation proven to have been created by this automation; it does not cancel unrelated invitations. Already accepted private-repository access is not removed automatically. Ask the maintainer for an access change, or remove yourself through GitHub; do not assume deleting a public comment or withdrawing approval terminates existing access. Keep access discussions free of private repository contents.

签署无效或已撤回、PR head 改变、PR 关闭或转为草稿，以及批准被撤销或被后续审阅取代，均会使新的自动邀请资格失效。同步任务只能取消准确证明确由本自动化创建、且仍待接受的邀请，不取消其他来源的邀请。已经接受的私有仓库权限不会自动移除。若需变更访问权限，请联系维护者，或在 GitHub 中自行退出；不要假设删除公开评论或撤回批准就会终止已有权限。讨论权限时也不要公开私有仓库内容。

## Maintainer operations / 维护者操作

### Permissions and trust boundaries / 权限与信任边界

`DapengFeng/wgpt` is a private personal-account repository. Its collaborators have read/write access; GitHub does not offer read-only collaborators for this repository type. Automatic invitations therefore grant write collaboration without repository administration. A valid CLA signature is necessary but not sufficient: the public repository owner must approve admission. The reconciler matches the human reviewer's numeric account ID to the owner ID from the verified public repository; collaborator permissions or displayed names are not substitutes. Protect private development/release branches and audit collaborator access accordingly. [GitHub's permission documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository) describes this boundary.

`DapengFeng/wgpt` 是个人账号下的私有仓库。其协作者具有读写权限；GitHub 不为这类仓库提供只读协作者。因此，自动邀请会授予写入协作权限，但不授予仓库管理权限。有效 CLA 签署是必要条件，但还须公开仓库所有者批准接入。同步任务将真人审阅者的数字账号 ID 与已核验公开仓库的所有者 ID 对应，协作者权限或显示名称均不能代替此核验。应相应保护私有开发/发布分支，并审计协作者权限。[GitHub 权限文档](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository)说明平台限制。

Only maintainers have write access to **public** wgpt-community. Fork authors contribute through PRs. CLA processing runs trusted public `main` code and reads PR/comment metadata as data; it must not check out or execute PR head code, contributor files, commands, dependencies or workflow changes. The regular public `GITHUB_TOKEN` manages comments, status and the signature ledger, and has no invitation authority for private wgpt.

只有维护者拥有**公开** wgpt-community 的写权限；fork 作者通过 PR 贡献。CLA 处理运行公开仓库 `main` 上的可信代码，将 PR/评论元数据作为数据读取，不得检出或执行 PR head 的代码、贡献者文件、命令、依赖或工作流改动。普通公开仓库 `GITHUB_TOKEN` 负责评论、状态及签署账本，没有邀请私有 wgpt 协作者的权限。

Create a personal **fine-grained PAT** owned by the private repository's administrator. Select only `DapengFeng/wgpt` and repository permission **Administration: Read and write**; do not grant all repositories or use a classic broad-scope token. Keep an expiration and rotation process. The [collaborator API](https://docs.github.com/en/rest/collaborators/collaborators#add-a-repository-collaborator) documents this required permission. The workflow must never print the token.

由私有仓库管理员创建个人 **fine-grained PAT**，仅选择 `DapengFeng/wgpt`，仓库权限设置为 **Administration: Read and write**；不要授予全部仓库或使用范围过大的 classic token。设置有效期并安排轮换。[协作者 API](https://docs.github.com/en/rest/collaborators/collaborators#add-a-repository-collaborator)说明了这一必需权限。工作流绝不能打印令牌。

Store it as `WGPT_COLLABORATOR_TOKEN` in the **public repository environment** `collaborator-invitations`. Configure that environment's selected deployment branches to allow only the `main` branch, with no tag or wildcard allowance. Do not put the token in ordinary private-repository secrets: newly admitted write collaborators can propose or run workflow changes there, so that storage would undermine this boundary. Configure [GitHub environment controls](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) before enabling invitations; merely naming an environment in YAML does not protect it.

将令牌以 `WGPT_COLLABORATOR_TOKEN` 保存到**公开仓库的 environment** `collaborator-invitations`，该环境的 selected deployment branches 仅允许 `main` 分支，不放行 tag 或通配规则。不要将令牌放入普通私有仓库 secret：新加入的写权限协作者可在那里提出或运行工作流变更，这种存储会破坏权限边界。启用邀请前须配置 [GitHub environment 控制](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)；仅在 YAML 中写出 environment 名称不能形成保护。

Protect public `main` with the `cla/signature` status bound to GitHub Actions (app ID `15368`) and one approving Code Owner review. Administrator bypass remains enabled for trusted bootstrap operations; it is an explicit exception to the ordinary PR gate, not proof that bypassed commits passed it. Keep administrator access limited and inspect any bootstrap change before it can run with the invitation credential.

公开 `main` 的保护要求绑定 GitHub Actions（app ID `15368`）的 `cla/signature` 状态，以及一次 Code Owner 批准审阅。为可信初始化操作保留管理员绕过权限；这是普通 PR 检查的明确例外，不代表被绕过的提交已通过检查。限制管理员范围，并在初始化变更能够使用邀请凭据运行前审阅其内容。

### Invitation timing and recovery / 邀请时序与恢复

The reconciler runs on trusted public `main` every 20 minutes and revalidates both the signature and current owner approval before sending an invitation. No invitation is sent while owner approval is missing; a valid signature alone does not start an invitation attempt. Existing collaborators and pending invitations are handled without granting administration. Expired, declined or otherwise ended invitations are not repeatedly recreated from an old signature; post a new exact signing comment and obtain a new owner approval after it to request another invitation. A green CLA status does not prove owner approval or that the token, permissions or GitHub invitation limits are configured correctly; inspect the workflow result before changing a signature.

邀请同步任务计划每 20 分钟在可信的公开 `main` 上运行，发出邀请前重新校验签署和当前所有者批准。缺少所有者批准时不会发送邀请；仅有有效签署不会开始邀请尝试。已有协作者和待接受邀请会按既有状态处理，不授予管理权限。过期、被拒绝或以其他方式结束的邀请，不会凭旧签署不断重建；须新发一条准确签署评论，再取得晚于该签署的新所有者批准，才能请求再次邀请。CLA 检查通过不能证明所有者已批准，或令牌、权限及 GitHub 邀请限额均配置正确；修改签署前应先检查工作流结果。

Each run permits at most 10 new invitation requests, and the rolling 24-hour budget permits at most 40 journaled `request_intent` records. The daily count includes new request attempts with an uncertain outcome, not just accepted invitations; observing existing access or an existing invitation does not consume that budget. Eligible requests beyond the limit wait for a later run. Do not erase the journal or repeat an uncertain request to bypass these limits.

每次运行最多发起 10 个新邀请请求，滚动 24 小时预算最多允许 40 条已记日志的 `request_intent`。日计数包含结果仍不确定的新请求尝试，并非只计算已经接受的邀请；观察到已有权限或已有邀请不消耗该预算。超过限制的有效请求等待后续运行。不要删除日志或重复结果不确定的请求来绕过限制。

Twenty minutes is a schedule, not a delivery deadline. GitHub may delay or drop scheduled jobs under load, and disables public scheduled workflows after 60 days without repository activity. Maintainers should inspect Actions, re-enable a disabled schedule or use manual dispatch from `main`, and rotate an expired token rather than posting it in an issue. [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) is the upstream contract.

20 分钟是计划周期，不是送达期限。GitHub 可能因负载延迟或丢弃定时任务，也会在公开仓库 60 天无活动后停用定时工作流。维护者应查看 Actions、重新启用被停用的计划，或从 `main` 手动调度；令牌过期时应轮换，不要在 issue 中贴出令牌。[GitHub 定时运行说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)是上游约定。

## Deployment and acceptance / 部署与验收

The existing owners are `scripts/cla.py` for signature/status/ledger processing and `scripts/invite_collaborators.py` for private-repository invitations. Keep their policy and workflow boundaries together when changing behavior. Run offline tests from public repository root:

现有职责归属为：`scripts/cla.py` 负责签署、状态和账本，`scripts/invite_collaborators.py` 负责私有仓库邀请。修改行为时一并核对它们的策略及工作流边界。在公开仓库根目录运行离线测试：

```bash
python3 -m unittest discover -s tests
```

Review the complete changes before deploying: trusted checkout, least-privilege workflow permissions, environment protection, exact agreement version/hash, GitHub numeric identity checks, edited/deleted signatures, owner approval after signing on the current head, dismissed/superseded reviews, changed/closed/draft PRs, unavailable GitHub data, duplicate delivery and already-pending invitations. Read every review page within the bounded paginator; incomplete or failed evidence reads must not grant eligibility or trigger cancellation. Recheck live evidence before recording send intent, and preserve the journal's uncertainty rules. Never execute contributor code with either a write-capable token or the invitation token.

部署前审阅完整变更：可信 checkout、最小工作流权限、environment 保护、准确协议版本/哈希、GitHub 数字身份核验、签署编辑/删除、签署后针对当前 head 的所有者批准、被撤销或取代的审阅、改动/关闭/草稿 PR、GitHub 数据不可用、重复投递及已有待接受邀请。使用有界分页器读取全部审阅页；依据不完整或读取失败不能授予资格，也不能触发取消。记录发送意图前重新核验实况，并保留日志对不确定结果的处理规则。绝不能使用持有写权限或邀请令牌的作业执行贡献者代码。

Hosted end-to-end acceptance is **not established by offline synthetic tests**. Record a real external-account fork/PR, the bot statement's version/hash, that account's signing-comment URL, the ledger entry and `cla/signature` result, the owner's later approval on the current head, one private-repository invitation and acceptance, and resulting write-without-admin permission. Verify that a signature without owner approval sends no invitation. Also exercise a changed head, dismissed approval, closed PR and edited/deleted signature before acceptance; cancellation must affect only an exact automation-owned pending invitation, never external invitations or accepted access. Confirm duplicate reconciliation creates no duplicate invitations. Record actual workflow revisions and outcomes without copying private source or secrets into public evidence. This acceptance remains open until those hosted observations exist.

**离线合成测试不能证明托管端到端验收通过。** 须记录真实外部账号的 fork/PR、bot 声明的版本/哈希、该账号的签署评论 URL、账本条目与 `cla/signature` 结果、所有者随后针对当前 head 的批准、一次私有仓库邀请及接受，以及最终的可写但无管理权限。验证仅签署但未获所有者批准时不发送邀请。还应在接受前覆盖 head 改变、批准被撤销、PR 关闭及签署编辑/删除；只能取消准确匹配的本自动化待接受邀请，不能影响外部邀请或已接受权限。确认重复同步不会重复邀请。记录实际工作流提交和结果，不向公开证据复制私有源码或 secret。取得这些托管观察结果前，此项验收保持未完成。
