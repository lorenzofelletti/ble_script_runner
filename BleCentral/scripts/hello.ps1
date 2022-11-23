# echoes hello and arg1 or world if no arg1
param(
    [string]$arg1 = "world"
)
write-host "Hello $arg1!"
