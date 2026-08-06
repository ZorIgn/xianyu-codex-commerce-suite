param(
  [Parameter(Mandatory=$true)][ValidateSet("snapshot","send","windows","prepare")][string]$Operation,
  [Parameter(Mandatory=$true)][int]$TargetPid,
  [string]$Prompt = "",
  [string]$PromptB64 = "",
  [int]$TimeoutSeconds = 180,
  [string]$HeartbeatPath = "",
  [bool]$AllowForegroundFallback = $false
)

$ErrorActionPreference = "Stop"
if ($PromptB64) {
  $Prompt = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($PromptB64))
}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
if (-not ("XianyuDesktopNativeInputV2" -as [type])) {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class XianyuDesktopNativeInputV2 {
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")]
  public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
}
"@
}
try {
  [void][XianyuDesktopNativeInputV2]::SetProcessDpiAwarenessContext([IntPtr](-4))
} catch {}

function Get-ElementValue {
  param([Parameter(Mandatory=$true)]$Element)
  try {
    $pattern = $Element.GetCurrentPattern(
      [System.Windows.Automation.ValuePattern]::Pattern
    )
    return [string]$pattern.Current.Value
  } catch {
    return ""
  }
}

function Invoke-AutomationElement {
  param([Parameter(Mandatory=$true)]$Element)
  try {
    $invoke = $Element.GetCurrentPattern(
      [System.Windows.Automation.InvokePattern]::Pattern
    )
    $invoke.Invoke()
    return $true
  } catch {}
  try {
    $legacy = $Element.GetCurrentPattern(
      [System.Windows.Automation.LegacyIAccessiblePattern]::Pattern
    )
    $legacy.DoDefaultAction()
    return $true
  } catch {}
  return $false
}

function Click-AutomationElement {
  param(
    [Parameter(Mandatory=$true)]$Window,
    [Parameter(Mandatory=$true)]$Element
  )
  if (-not $AllowForegroundFallback) { return $false }
  try {
    $point = $Element.GetClickablePoint()
    $handle = [IntPtr]([int64]$Window.Current.NativeWindowHandle)
    if ($handle -ne [IntPtr]::Zero) {
      [void][XianyuDesktopNativeInputV2]::SetForegroundWindow($handle)
      Start-Sleep -Milliseconds 120
    }
    if (-not [XianyuDesktopNativeInputV2]::SetCursorPos(
      [int][Math]::Round($point.X),
      [int][Math]::Round($point.Y)
    )) { return $false }
    Start-Sleep -Milliseconds 80
    [XianyuDesktopNativeInputV2]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    [XianyuDesktopNativeInputV2]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    return $true
  } catch {
    return $false
  }
}

function Find-SendControl {
  param([Parameter(Mandatory=$true)]$Window)
  $elements = Get-Descendants $Window
  $fallback = $null
  for ($i = 0; $i -lt $elements.Count; $i++) {
    $element = $elements.Item($i)
    if ($element.Current.ControlType.ProgrammaticName -ne "ControlType.Button") { continue }
    if (-not $element.Current.IsEnabled -or $element.Current.IsOffscreen) { continue }
    $name = ([string]$element.Current.Name).Trim()
    if ($name -match "(?i)^(发送|发送消息|提交|Send|Send message|Submit)$") {
      return $element
    }
    $automationId = ([string]$element.Current.AutomationId).Trim()
    if (
      $null -eq $fallback -and
      $automationId -match "(?i)^(send|submit|composer[-_]?send|prompt[-_]?submit)$"
    ) {
      $fallback = $element
    }
  }
  return $fallback
}

function Update-BridgeHeartbeat {
  if ([string]::IsNullOrWhiteSpace($HeartbeatPath)) { return }
  try {
    $payload = [ordered]@{
      pid = $PID
      ready = $true
      updated_at = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json -Compress
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($payload)
    $stream = [System.IO.FileStream]::new(
      $HeartbeatPath,
      [System.IO.FileMode]::OpenOrCreate,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::ReadWrite
    )
    try {
      $stream.SetLength(0)
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Flush()
    } finally {
      $stream.Dispose()
    }
  } catch {
    # Heartbeat failures must not interrupt UI Automation.
  }
}
function Get-TargetProcessIds {
  $ids = [System.Collections.Generic.HashSet[int]]::new()
  [void]$ids.Add($TargetPid)
  try {
    $processes = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId)
    $changed = $true
    while ($changed) {
      $changed = $false
      foreach ($process in $processes) {
        $parent = [int]$process.ParentProcessId
        $child = [int]$process.ProcessId
        if ($child -gt 0 -and $ids.Contains($parent) -and $ids.Add($child)) {
          $changed = $true
        }
      }
    }
  } catch {
    # Exact PID matching remains available if process-tree discovery is unavailable.
  }
  return ,$ids
}

function Get-Window {
  $targetIds = Get-TargetProcessIds
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $windows = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  $best = $null
  $bestScore = -1
  for ($i = 0; $i -lt $windows.Count; $i++) {
    $candidate = $windows.Item($i)
    if (-not $targetIds.Contains([int]$candidate.Current.ProcessId)) { continue }

    # The process exposes both an empty Codex shell and the real conversation
    # window. Select the candidate containing a usable composer.
    $score = 0
    $name = [string]$candidate.Current.Name
    if ($name -match "(?i)^ChatGPT$") { $score += 100 }
    elseif ($name -match "(?i)Codex|ChatGPT") { $score += 20 }
    try {
      $descendants = Get-Descendants $candidate
      $score += [Math]::Min($descendants.Count, 50)
      for ($j = 0; $j -lt $descendants.Count; $j++) {
        $element = $descendants.Item($j)
        if (
          $element.Current.ControlType.ProgrammaticName -eq "ControlType.Edit" -and
          $element.Current.IsEnabled -and
          -not $element.Current.IsOffscreen
        ) {
          $score += 1000
          break
        }
      }
    } catch {}
    if ($score -gt $bestScore) {
      $best = $candidate
      $bestScore = $score
    }
  }
  if ($null -ne $best) { return $best }
  throw "bound desktop window not found for process tree $TargetPid"
}
function Get-Descendants($window) {
  return $window.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
}

function Get-Snapshot($window) {
  $elements = Get-Descendants $window
  $texts = New-Object System.Collections.Generic.List[string]
  $buttons = New-Object System.Collections.Generic.List[string]
  for ($i = 0; $i -lt $elements.Count; $i++) {
    $element = $elements.Item($i)
    $name = [string]$element.Current.Name
    if ([string]::IsNullOrWhiteSpace($name)) { continue }
    $type = $element.Current.ControlType.ProgrammaticName
    if ($type -eq "ControlType.Text" -or $type -eq "ControlType.Document") {
      [void]$texts.Add($name)
    } elseif ($type -eq "ControlType.Button") {
      [void]$buttons.Add($name)
    }
  }
  $loginVisible = @($texts | Where-Object {
    $_ -match "登录 ChatGPT|Log in to ChatGPT|Sign in to ChatGPT"
  }).Count -gt 0
  $onboardingVisible = @($texts | Where-Object {
    $_ -match "欢迎使用 ChatGPT 桌面版|哪一项最能描述您的工作|选择您的工作类型|Welcome to ChatGPT|what best describes your work|personalization"
  }).Count -gt 0
  $composerReady = $false
  $composerInfo = $null
  $sendInfo = $null
  try {
    $candidateComposer = Find-Composer $window
    $composerReady = (
      $null -ne $candidateComposer -and
      -not $loginVisible -and
      -not $onboardingVisible
    )
    $rect = $candidateComposer.Current.BoundingRectangle
    $composerInfo = [pscustomobject]@{
      name = [string]$candidateComposer.Current.Name
      automation_id = [string]$candidateComposer.Current.AutomationId
      value = Get-ElementValue $candidateComposer
      keyboard_focusable = [bool]$candidateComposer.Current.IsKeyboardFocusable
      has_keyboard_focus = [bool]$candidateComposer.Current.HasKeyboardFocus
      x = [double]$rect.X
      y = [double]$rect.Y
      width = [double]$rect.Width
      height = [double]$rect.Height
    }
    $candidateSend = Find-SendControl $window
    if ($null -ne $candidateSend) {
      $sendRect = $candidateSend.Current.BoundingRectangle
      $sendInfo = [pscustomobject]@{
        name = [string]$candidateSend.Current.Name
        automation_id = [string]$candidateSend.Current.AutomationId
        keyboard_focusable = [bool]$candidateSend.Current.IsKeyboardFocusable
        has_keyboard_focus = [bool]$candidateSend.Current.HasKeyboardFocus
        x = [double]$sendRect.X
        y = [double]$sendRect.Y
        width = [double]$sendRect.Width
        height = [double]$sendRect.Height
      }
    }
  } catch {
    $composerReady = $false
  }
  [pscustomobject]@{
    texts = @($texts)
    buttons = @($buttons)
    window = $window.Current.Name
    process_id = [int]$window.Current.ProcessId
    composer_ready = $composerReady
    composer = $composerInfo
    send_control = $sendInfo
    login_visible = $loginVisible
    onboarding_visible = $onboardingVisible
  }
}

function Find-Composer($window) {
  $elements = Get-Descendants $window
  $fallback = $null
  for ($i = 0; $i -lt $elements.Count; $i++) {
    $element = $elements.Item($i)
    if ($element.Current.ControlType.ProgrammaticName -ne "ControlType.Edit") { continue }
    if (-not $element.Current.IsEnabled -or $element.Current.IsOffscreen) { continue }
    if ($null -eq $fallback) { $fallback = $element }
    $name = [string]$element.Current.Name
    if ($name -match "随心输入|输入|message|Message|prompt|Prompt") {
      return $element
    }
  }
  if ($null -ne $fallback) { return $fallback }
  throw "Codex composer edit control not found"
}

function Invoke-NamedElement {
  param(
    [Parameter(Mandatory=$true)]$Window,
    [Parameter(Mandatory=$true)][string[]]$Names
  )

  $elements = Get-Descendants $Window
  foreach ($wanted in $Names) {
    for ($i = 0; $i -lt $elements.Count; $i++) {
      $element = $elements.Item($i)
      if ([string]$element.Current.Name -ne $wanted) { continue }
      if (-not $element.Current.IsEnabled -or $element.Current.IsOffscreen) { continue }
      try {
        $selection = $element.GetCurrentPattern(
          [System.Windows.Automation.SelectionItemPattern]::Pattern
        )
        $selection.Select()
        return $true
      } catch {}
      try {
        $invoke = $element.GetCurrentPattern(
          [System.Windows.Automation.InvokePattern]::Pattern
        )
        $invoke.Invoke()
        return $true
      } catch {}
      try {
        $legacy = $element.GetCurrentPattern(
          [System.Windows.Automation.LegacyIAccessiblePattern]::Pattern
        )
        $legacy.DoDefaultAction()
        return $true
      } catch {}
    }
  }
  return $false
}
Update-BridgeHeartbeat
if ($Operation -eq "windows") {
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $windows = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  $items = @()
  for ($i = 0; $i -lt $windows.Count; $i++) {
    $candidate = $windows.Item($i)
    if ([string]::IsNullOrWhiteSpace([string]$candidate.Current.Name)) { continue }
    $items += [pscustomobject]@{
      process_id = [int]$candidate.Current.ProcessId
      window = [string]$candidate.Current.Name
    }
  }
  [pscustomobject]@{ windows = $items } | ConvertTo-Json -Compress -Depth 4
  return
}

$window = Get-Window
if ($Operation -eq "prepare") {
  $before = Get-Snapshot $window
  if (-not $before.onboarding_visible) {
    $newChat = Invoke-NamedElement -Window $window -Names @(
      "新对话", "New chat"
    )
    Start-Sleep -Milliseconds 750
    $afterPrepare = Get-Snapshot $window
    [pscustomobject]@{
      handled = $newChat
      new_chat = $newChat
      composer_ready = $afterPrepare.composer_ready
      login_visible = $afterPrepare.login_visible
      window = $afterPrepare.window
    } | ConvertTo-Json -Compress -Depth 4
    return
  }

  $selected = Invoke-NamedElement -Window $window -Names @(
    "工程", "Engineering", "学生", "Student"
  )
  Start-Sleep -Milliseconds 250
  $continued = Invoke-NamedElement -Window $window -Names @(
    "继续", "Continue", "下一步", "Next", "开始使用", "Get started",
    "完成", "Done", "跳过", "Skip", "以后再说", "Not now"
  )
  Start-Sleep -Milliseconds 750
  Update-BridgeHeartbeat
  [pscustomobject]@{
    handled = ($selected -or $continued)
    selected = $selected
    continued = $continued
  } | ConvertTo-Json -Compress -Depth 4
  return
}

if ($Operation -eq "snapshot") {
  Get-Snapshot $window | ConvertTo-Json -Compress -Depth 4
  return
}

if ([string]::IsNullOrWhiteSpace($Prompt)) {
  throw "prompt is empty"
}

$before = Get-Snapshot $window
$beforeSignature = [string]::Join([Environment]::NewLine, @($before.texts))
$composer = Find-Composer $window
$inputMethod = ""
$submittedBy = ""
$promptVerified = $false
try {
  $valuePattern = $composer.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  $valuePattern.SetValue($Prompt)
  Start-Sleep -Milliseconds 150
  $promptVerified = ([string]$valuePattern.Current.Value -eq $Prompt)
  if (-not $promptVerified) { throw "ValuePattern 写入后回读不一致" }
  $inputMethod = "value_pattern"
} catch {
  if (-not $AllowForegroundFallback) { throw "ValuePattern 写入失败；后台模式已禁用前台 fallback" }
  $clipboardHadText = [System.Windows.Forms.Clipboard]::ContainsText()
  $clipboardText = if ($clipboardHadText) { [System.Windows.Forms.Clipboard]::GetText() } else { "" }
  try {
    [System.Windows.Forms.Clipboard]::SetText($Prompt)
    $window.SetFocus()
    $composer.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait("^v")
  } finally {
    if ($clipboardHadText) {
      [System.Windows.Forms.Clipboard]::SetText($clipboardText)
    } else {
      [System.Windows.Forms.Clipboard]::Clear()
    }
  }
  Start-Sleep -Milliseconds 150
  $promptVerified = ((Get-ElementValue $composer) -eq $Prompt)
  if (-not $promptVerified) { throw "无法确认已把你好写入 Codex 输入框" }
  $inputMethod = "clipboard"
}

$sendControl = Find-SendControl $window
if ($null -ne $sendControl -and (Invoke-AutomationElement $sendControl)) {
  $submittedBy = "button"
}

# UIA InvokePattern can report success even when Electron ignores the click.
# Confirm that the composer was cleared (or generation started); otherwise
# focus the exact composer and submit with Enter as a deterministic fallback.
Start-Sleep -Milliseconds 600
$postSubmit = Get-Snapshot $window
$postSignature = [string]::Join([Environment]::NewLine, @($postSubmit.texts))
$stopVisible = @($postSubmit.buttons | Where-Object { $_ -match "停止|Stop|Cancel" }).Count -gt 0
$remainingValue = ""
try { $remainingValue = Get-ElementValue (Find-Composer $window) } catch {}
if ($remainingValue -eq $Prompt -and -not $stopVisible) {
  $buttonKeySubmitted = $false
  if ($AllowForegroundFallback -and $null -ne $sendControl) {
    try {
      $window.SetFocus()
      $sendControl.SetFocus()
      Start-Sleep -Milliseconds 100
      [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
      $buttonKeySubmitted = $true
      $submittedBy = if ($submittedBy) { "button_then_button_enter" } else { "button_enter" }
    } catch {}
  }
  if ($buttonKeySubmitted) {
    Start-Sleep -Milliseconds 800
    $postSubmit = Get-Snapshot $window
    $postSignature = [string]::Join([Environment]::NewLine, @($postSubmit.texts))
    $stopVisible = @($postSubmit.buttons | Where-Object { $_ -match "停止|Stop|Cancel" }).Count -gt 0
    $remainingValue = ""
    try { $remainingValue = Get-ElementValue (Find-Composer $window) } catch {}
  }
}
if ($AllowForegroundFallback -and $remainingValue -eq $Prompt -and -not $stopVisible) {
  if ($null -ne $sendControl -and (Click-AutomationElement -Window $window -Element $sendControl)) {
    $submittedBy = if ($submittedBy) { "$submittedBy`_then_click" } else { "button_click" }
    Start-Sleep -Milliseconds 800
    $postSubmit = Get-Snapshot $window
    $postSignature = [string]::Join([Environment]::NewLine, @($postSubmit.texts))
    $stopVisible = @($postSubmit.buttons | Where-Object { $_ -match "停止|Stop|Cancel" }).Count -gt 0
    $remainingValue = ""
    try { $remainingValue = Get-ElementValue (Find-Composer $window) } catch {}
  }
}
if ($AllowForegroundFallback -and $remainingValue -eq $Prompt -and -not $stopVisible) {
  try {
    $composer = Find-Composer $window
    if (-not (Click-AutomationElement -Window $window -Element $composer)) {
      throw "无法点击 Codex 输入框"
    }
    Start-Sleep -Milliseconds 150
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    $submittedBy = if ($submittedBy) { "$submittedBy`_then_enter" } else { "enter" }
  } catch {
    throw "你好已写入输入框，但发送按钮和 Enter 都无法执行: $($_.Exception.Message)"
  }
  Start-Sleep -Milliseconds 800
  $postSubmit = Get-Snapshot $window
  $postSignature = [string]::Join([Environment]::NewLine, @($postSubmit.texts))
  $stopVisible = @($postSubmit.buttons | Where-Object { $_ -match "停止|Stop|Cancel" }).Count -gt 0
  $remainingValue = ""
  try { $remainingValue = Get-ElementValue (Find-Composer $window) } catch {}
}
if ($remainingValue -eq $Prompt -and -not $stopVisible) {
  throw "你好已写入，但发送动作没有生效"
}

$submissionAccepted = ($remainingValue -ne $Prompt -or $stopVisible)
$started = Get-Date
$seenChange = ($postSignature -ne $beforeSignature)
$sawStop = $stopVisible
$hasStop = $stopVisible
$stable = 0
$previousSignature = $postSignature
$after = $postSubmit

while (((Get-Date) - $started).TotalSeconds -lt $TimeoutSeconds) {
  Start-Sleep -Milliseconds 250
  Update-BridgeHeartbeat
  $after = Get-Snapshot $window
  $signature = [string]::Join([Environment]::NewLine, @($after.texts))
  $hasStop = @($after.buttons | Where-Object { $_ -match "停止|Stop|Cancel" }).Count -gt 0
  if ($hasStop) { $sawStop = $true }
  if ($signature -ne $beforeSignature) { $seenChange = $true }

  if ($seenChange -and -not $hasStop) {
    if ($signature -eq $previousSignature) { $stable++ } else { $stable = 0 }
  } else {
    $stable = 0
  }
  $previousSignature = $signature
  $replyShapeVisible = $after.texts.Count -ge ($before.texts.Count + 2)
  if ($sawStop -and $seenChange -and -not $hasStop -and $stable -ge 6) { break }
  if (
    $submissionAccepted -and $seenChange -and -not $hasStop -and
    $replyShapeVisible -and $stable -ge 16
  ) { break }
}

$changedTexts = New-Object System.Collections.Generic.List[string]
$ignoredReplyPattern = "^(随心输入|输入消息|发送消息|请输入|Message|Send a message|Ask anything|暂无来源|无来源|请求批准|Codex|ChatGPT|ChatGPT 说[:：]?|停止|Stop|取消|Cancel|\d{1,2}:\d{2})$"
for ($i = 0; $i -lt $after.texts.Count; $i++) {
  $current = ([string]$after.texts[$i]).Trim()
  $previous = if ($i -lt $before.texts.Count) { ([string]$before.texts[$i]).Trim() } else { "" }
  if ([string]::IsNullOrWhiteSpace($current)) { continue }
  if ($current -eq $Prompt -or $current.Length -gt 4000) { continue }
  if ($current -match $ignoredReplyPattern) { continue }
  if ($current -ne $previous) { [void]$changedTexts.Add($current) }
}

$timedOut = (((Get-Date) - $started).TotalSeconds -ge $TimeoutSeconds)
$completedWithoutObservedStop = (
  $submissionAccepted -and $seenChange -and -not $hasStop -and
  $after.texts.Count -ge ($before.texts.Count + 2) -and
  $stable -ge 16 -and -not $timedOut
)
$generationCompleted = (
  ($sawStop -and $seenChange -and -not $hasStop -and -not $timedOut) -or
  $completedWithoutObservedStop
)
$reply = ""
if ($changedTexts.Count -gt 0) {
  $reply = $changedTexts[$changedTexts.Count - 1]
} elseif ($generationCompleted) {
  $reply = "Codex 已完成回复"
}

[pscustomobject]@{
  ok = $generationCompleted
  sent = $true
  response_detected = $generationCompleted
  activity_observed = $sawStop
  generation_completed = $generationCompleted
  reply = $reply
  timed_out = $timedOut
  saw_stop = $sawStop
  prompt_verified = $promptVerified
  input_method = $inputMethod
  submitted_by = $submittedBy
} | ConvertTo-Json -Compress -Depth 4
