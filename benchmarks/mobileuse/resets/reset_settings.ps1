Write-Output "Resetting Settings baseline state for benchmark task..."

if (Get-Command adb -ErrorAction SilentlyContinue) {
    adb shell input keyevent 3 | Out-Null
    Start-Sleep -Seconds 1
    adb shell am start -a android.settings.SETTINGS | Out-Null
    Start-Sleep -Seconds 2
    adb shell input keyevent 4 | Out-Null
}

Write-Output "Settings reset complete."
exit 0
