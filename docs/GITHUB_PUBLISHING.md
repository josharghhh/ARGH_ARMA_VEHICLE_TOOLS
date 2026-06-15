# Publish This Repository And Website

This folder is ready to become its own GitHub repository.

## Using GitHub Desktop

1. Open GitHub Desktop.
2. Choose **File > Add Local Repository**.
3. Select the `Reforger-Vehicle-Tools` folder.
4. If GitHub Desktop says it is not a repository, choose **Create a Repository**.
5. Use repository name `Reforger-Vehicle-Tools`.
6. Commit all files with message `Initial Reforger Vehicle Tools release`.
7. Click **Publish repository**.
8. Open the repository on GitHub.
9. Open **Settings > Pages**.
10. Under **Build and deployment**, choose **GitHub Actions**.

The included `pages.yml` workflow builds the addon ZIP and deploys the `docs` website.

## Using Git

From this folder:

```bash
git init
git add .
git commit -m "Initial Reforger Vehicle Tools release"
git branch -M main
git remote add origin https://github.com/YOUR-NAME/Reforger-Vehicle-Tools.git
git push -u origin main
```

Then enable **GitHub Actions** under the repository's Pages settings.

## Create A GitHub Release

1. Open the repository's **Releases** page.
2. Choose **Draft a new release**.
3. Create a tag such as `v0.8.6`.
4. Use the matching section from `CHANGELOG.md`.
5. Upload `dist/reforger_vehicle_checker.zip`.
6. Publish the release.

## Website

The Pages workflow publishes:

- Project overview.
- Beginner guide.
- Collision reference.
- Dependency guide.
- Direct addon ZIP download.
