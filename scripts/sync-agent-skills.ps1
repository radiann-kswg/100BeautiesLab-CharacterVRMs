<#
.SYNOPSIS
    エージェントスキルの正本 (.agents/skills/) を、Claude 用ミラー (.claude/skills/) へ同期する。

.DESCRIPTION
    本リポジトリ（100BeautiesLab-CharacterVRMs）はエージェント設定を SSOT で管理している（正典は AGENTS.md）。
    スキルについても同様に、ベンダー中立な .agents/skills/ を「正本（実体）」とし、
    .claude/skills/ を「生成ミラー」として扱う。

      .agents/skills/<skill>/   ← 正本。GPT Codex がプロジェクトスキルとして読む。編集はここ
      .claude/skills/<skill>/   ← 生成ミラー。Claude Code / Cowork が読む。直接編集しない

    処理対象は「正本に存在するスキル」のみ。ミラー側にしか無いスキルは削除せず警告する
    （手動で入れた別スキルを巻き込まないため）。
    repo_path.txt と __pycache__ は環境固有のため同期対象から除外する。

.PARAMETER Check
    差分の有無だけを表示する。差分があれば exit 1（CI / 作業前確認向け）。既定の動作。

.PARAMETER Apply
    正本 -> ミラーへ実際に反映する（不足・変更をコピーし、ミラー側の余分なファイルを削除）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\sync-agent-skills.ps1 -Check
    powershell -ExecutionPolicy Bypass -File scripts\sync-agent-skills.ps1 -Apply

.NOTES
    詳細: AGENTS.md §11（入口ファイルとの関係）
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

# 引数なしは -Check 扱い（安全側）
if (-not $Apply) { $Check = $true }

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SrcRoot  = Join-Path $RepoRoot '.agents\skills'
$DstRoot  = Join-Path $RepoRoot '.claude\skills'

# 環境固有 / ビルド生成物は同期しない
$ExcludeNames = @('repo_path.txt')
$ExcludeDirs  = @('__pycache__')
$ExcludeExts  = @('.skill')

if (-not (Test-Path $SrcRoot)) {
    Write-Error "スキル正本が見つかりません: $SrcRoot"
    exit 2
}

Write-Host "== エージェントスキル同期 ==" -ForegroundColor Cyan
Write-Host ("モード : {0}" -f $(if ($Apply) { 'Apply (正本 -> ミラー)' } else { 'Check (差分表示のみ)' }))
Write-Host "正本   : $SrcRoot"
Write-Host "ミラー : $DstRoot"

function Get-RelativeFiles {
    param([string]$Root)
    if (-not (Test-Path $Root)) { return @() }
    $prefix = (Resolve-Path $Root).Path.TrimEnd('\') + '\'
    $items = Get-ChildItem -Path $Root -Recurse -File -Force
    $rel = @()
    foreach ($item in $items) {
        if ($ExcludeNames -contains $item.Name) { continue }
        if ($ExcludeExts -contains $item.Extension) { continue }
        $relPath = $item.FullName.Substring($prefix.Length)
        if (@($relPath.Split('\') | Where-Object { $ExcludeDirs -contains $_ }).Count -gt 0) { continue }
        $rel += $item.FullName.Substring($prefix.Length)
    }
    return $rel
}

$skills = @(Get-ChildItem -Path $SrcRoot -Directory -Force | Select-Object -ExpandProperty Name)
if ($skills.Count -eq 0) {
    Write-Host "同期対象のスキルがありません。終了します。"
    exit 0
}

$totalDiff = 0
$report    = @()

foreach ($skill in $skills) {
    $src = Join-Path $SrcRoot $skill
    $dst = Join-Path $DstRoot $skill

    $srcFiles = @(Get-RelativeFiles $src)
    $dstFiles = @(Get-RelativeFiles $dst)

    $missing = @($srcFiles | Where-Object { $dstFiles -notcontains $_ })
    $extra   = @($dstFiles | Where-Object { $srcFiles -notcontains $_ })
    $changed = @()

    foreach ($rel in $srcFiles) {
        if ($dstFiles -notcontains $rel) { continue }
        $hashA = (Get-FileHash (Join-Path $src $rel) -Algorithm SHA256).Hash
        $hashB = (Get-FileHash (Join-Path $dst $rel) -Algorithm SHA256).Hash
        if ($hashA -ne $hashB) { $changed += $rel }
    }

    $diffCount = $missing.Count + $extra.Count + $changed.Count
    $totalDiff += $diffCount
    $report += [pscustomobject]@{
        Skill = $skill; Missing = $missing.Count; Changed = $changed.Count; Extra = $extra.Count
    }

    if ($diffCount -eq 0) {
        Write-Host ("`n[{0}] 差分なし" -f $skill) -ForegroundColor Green
        continue
    }

    Write-Host ("`n[{0}] 差分 {1} 件" -f $skill, $diffCount) -ForegroundColor Yellow
    foreach ($f in $missing) { Write-Host ("  + ミラーに無い    : {0}" -f $f) }
    foreach ($f in $changed) { Write-Host ("  ~ 内容が異なる    : {0}" -f $f) }
    foreach ($f in $extra)   { Write-Host ("  - ミラー側に余分  : {0}" -f $f) }

    if (-not $Apply) { continue }

    foreach ($rel in ($missing + $changed)) {
        $to = Join-Path $dst $rel
        $toDir = Split-Path -Parent $to
        if (-not (Test-Path $toDir)) { New-Item -ItemType Directory -Force -Path $toDir | Out-Null }
        Copy-Item (Join-Path $src $rel) $to -Force
    }
    foreach ($rel in $extra) {
        Remove-Item (Join-Path $dst $rel) -Force
    }

    # 空になったディレクトリを掃除（深い順に削除）
    if (Test-Path $dst) {
        Get-ChildItem -Path $dst -Recurse -Directory -Force |
            Sort-Object { $_.FullName.Length } -Descending |
            ForEach-Object {
                if (-not (Get-ChildItem -Path $_.FullName -Force)) { Remove-Item $_.FullName -Force }
            }
    }
    Write-Host ("  -> 反映完了: {0}" -f $dst) -ForegroundColor Green
}

# --- ミラー側にしか無いスキルの警告（削除はしない） ---
if (Test-Path $DstRoot) {
    $orphans = @(Get-ChildItem -Path $DstRoot -Directory -Force |
        Where-Object { $skills -notcontains $_.Name } |
        Select-Object -ExpandProperty Name)
    foreach ($o in $orphans) {
        Write-Warning ("ミラーにのみ存在するスキル: {0} （正本 .agents/skills/ に無い。手動で確認してください）" -f $o)
    }
}

Write-Host "`n-- サマリ --" -ForegroundColor Yellow
$report | Format-Table Skill, Missing, Changed, Extra -AutoSize

if ($Apply) {
    Write-Host "同期完了。git status で .claude/skills/ の変更を確認してコミットしてください。" -ForegroundColor Green
    exit 0
}

if ($totalDiff -gt 0) {
    Write-Host ("差分 {0} 件。`-Apply` で正本の内容をミラーへ反映してください。" -f $totalDiff) -ForegroundColor Yellow
    exit 1
}

Write-Host "正本とミラーは一致しています。" -ForegroundColor Green
exit 0
