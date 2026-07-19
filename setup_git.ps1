$ErrorActionPreference = "Stop"

$env:GIT_TERMINAL_PROMPT=0

$token = "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"
$repoName = "Case-Comp"

$response = Invoke-WebRequest -Uri "https://api.github.com/repos/ed22b018-code/$repoName" -Headers @{Authorization="token $token"} -ErrorAction SilentlyContinue

if ($response.StatusCode -eq 200) {
    Write-Host "Repo already exists."
} else {
    Write-Host "Creating private repo..."
    Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post -Headers @{Authorization="token $token"; Accept="application/vnd.github.v3+json"} -Body (@{name=$repoName; private=$true} | ConvertTo-Json)
}

git init
git add .
git commit -m "Final MAI pipeline: Hybrid forecaster, K-Means clustering, and UI simulator"
git branch -M main

git config credential.helper ""
git config core.askPass ""

$remoteExists = git remote | Select-String "origin"
if (-not $remoteExists) {
    git remote add origin "https://ed22b018-code:$token@github.com/ed22b018-code/$repoName.git"
} else {
    git remote set-url origin "https://ed22b018-code:$token@github.com/ed22b018-code/$repoName.git"
}

git push -u origin main
