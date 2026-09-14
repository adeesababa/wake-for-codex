# Publish Wake on GitHub

The repository and documentation page are prepared locally. Publishing requires access to your GitHub account. No GitHub repository or live URL is implied by these files.

With the official GitHub CLI installed and authenticated, run from this folder:

```sh
gh auth status
git add .gitignore wake.py test_wake.py README.md BUSINESS.md PUBLISH.md docs .github
git commit -m "Build Wake usage-reset resumer and documentation"
git branch -M main
gh repo create wake-for-codex --public --source=. --remote=origin --push
```

In the new repository, open **Settings → Pages → Build and deployment → Source → GitHub Actions**. Run **Actions → Publish documentation → Run workflow** if necessary. The successful deployment displays the real page URL. No placeholder username is embedded in the page.

Alternatively, create a public repository on GitHub and upload the listed files, preserving directories. Never upload `.schema`, `.wake-codex`, credentials, task histories, or your project files.

This is a documentation site. GitHub Pages [does not permit sites primarily facilitating commercial transactions](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). A future paid product storefront should use a suitable commercial host. No license grant is added while the distribution model is undecided; choose licensing terms before public release.
