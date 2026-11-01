# OpenSDLC for claude.ai

`opensdlc-intent` lets product owners, designers, support and anyone else who does not use Claude Code capture an intent in claude.ai. Claude interviews them about the problem, writes `intent.md` from the same template the plugin uses, and either opens it as a pull request through a GitHub connector or hands it over as a download.

## Install

1. Zip the `opensdlc-intent` folder, so the archive holds `opensdlc-intent/SKILL.md` and `opensdlc-intent/template.md`.
2. Upload the zip as a custom skill in claude.ai, for yourself or, as an organization owner, for your whole organization. The [Claude help center](https://support.claude.com) describes where skills are managed on each plan.
3. For the pull request route, connect GitHub with access to the product repository.

## Keep it in step

`template.md` must stay identical to `plugin/skills/intent/template.md`; the test suite fails when they drift. Re-upload the zip after any change to either file.
