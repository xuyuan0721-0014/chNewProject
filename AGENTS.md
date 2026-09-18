# Repository Guidelines

## Project Structure & Module Organization

This is a Chinese-language research and worldbuilding repository, not an application. `灵感.md` is the root working notebook for themes, setting rules, and story ideas. `参考/` contains the curated reference corpus; most topics use descriptive Markdown files such as `参考/瘟神语料.md` or `参考/祭祀.md`. A few `.docx` files are retained as source snapshots beside related Markdown material. `daizhigev20-master/` and `daizhigev20-master.zip` are large local corpora excluded by `.gitignore`; never force-add them.

## Editing and Validation Commands

There is no build system or automated test suite. Use these checks before submitting changes:

```powershell
git status --short
git diff --check
git diff --word-diff -- "*.md"
```

The first command confirms the intended file set, the second catches whitespace errors, and the third makes prose edits easier to review. Preview changed Markdown in a renderer and confirm Chinese text remains UTF-8 encoded.

## Writing Style & Naming Conventions

Write primarily in clear Simplified Chinese. Organize long references with one `#` title followed by ordered `##` and `###` sections; keep a blank line around headings and lists. Follow existing patterns such as numbered subsections and bold labels (`**典故内涵**`). Prefer descriptive Chinese filenames: `<主题>语料.md` for collected material and `<主题>.md` for focused surveys. Distinguish sourced history from original setting ideas. Verify primary-text quotations against the local corpus and record the work, chapter, and source path. Keep edits narrow; avoid reformatting an entire document for a small content change.

## Review Guidelines

Because validation is editorial, inspect heading hierarchy, list numbering, punctuation, duplicate passages, and factual names or dates. When adding binary source material, also provide or update a readable Markdown counterpart when practical. Do not commit editor caches, generated exports, or ignored corpora.

## Commit & Pull Request Guidelines

Recent commits use short Chinese summaries, commonly `参考：新增<主题>语料` or `参考：新增…；更新灵感.md`. Keep one coherent topic per commit and use the same `范围：动作` pattern. Pull requests should summarize the purpose, list affected documents, identify major sources, and call out any speculative synthesis. Link related issues when available; screenshots are only needed for formatting-sensitive changes.
