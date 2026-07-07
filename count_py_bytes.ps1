$dirs = @(
    "pydantic-v1/docs/examples",
    "pydantic-v1/pydantic",
    "pydantic-v2/pydantic",
    "pydantic-v2/pydantic/deprecated",
    "pydantic-v2/pydantic/experimental"
)

$grand = 0
foreach ($d in $dirs) {
    $files = Get-ChildItem $d -Filter "*.py" -File
    $bytes = ($files | Measure-Object Length -Sum).Sum
    $grand += $bytes
    "{0,-40} {1,4} files  {2,10:N0} bytes" -f $d, $files.Count, $bytes
}
"{0,-40} {1,16:N0} bytes  (~{2:N0} tokens)" -f "TOTAL", $grand, ($grand / 4)