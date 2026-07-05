# verify-migration-notes.ps1
# Run from the folder that CONTAINS pydantic-v1/ and pydantic-v2/
#   PS> .\verify-migration-notes.ps1
# Results print to console AND save to verification-results.txt (share that file).
#
# Each check greps a source file for a literal string.
#   Expect = Present -> the symbol SHOULD exist there   (PASS if found)
#   Expect = Absent  -> the symbol should NOT exist there (PASS if not found)
# Absence checks are weaker evidence (grep can't prove semantics), but a
# "def foo(" that isn't there is a strong signal the method doesn't exist.

$checks = @(
    # ---------- BaseModel methods: v1 side ----------
    @{ Claim = "v1 has .dict()";                Path = "pydantic-v1/pydantic/main.py"; Pattern = "def dict(";                 Expect = "Present" },
    @{ Claim = "v1 has .json()";                Path = "pydantic-v1/pydantic/main.py"; Pattern = "def json(";                 Expect = "Present" },
    @{ Claim = "v1 has .parse_obj()";           Path = "pydantic-v1/pydantic/main.py"; Pattern = "def parse_obj(";            Expect = "Present" },
    @{ Claim = "v1 has .parse_raw()";           Path = "pydantic-v1/pydantic/main.py"; Pattern = "def parse_raw(";            Expect = "Present" },
    @{ Claim = "v1 has .parse_file()";          Path = "pydantic-v1/pydantic/main.py"; Pattern = "def parse_file(";           Expect = "Present" },
    @{ Claim = "v1 has .from_orm()";            Path = "pydantic-v1/pydantic/main.py"; Pattern = "def from_orm(";             Expect = "Present" },
    @{ Claim = "v1 has .construct()";           Path = "pydantic-v1/pydantic/main.py"; Pattern = "def construct(";            Expect = "Present" },
    @{ Claim = "v1 has .copy()";                Path = "pydantic-v1/pydantic/main.py"; Pattern = "def copy(";                 Expect = "Present" },
    @{ Claim = "v1 has .schema()  <-- the corrected row";      Path = "pydantic-v1/pydantic/main.py"; Pattern = "def schema(";      Expect = "Present" },
    @{ Claim = "v1 has .schema_json()";         Path = "pydantic-v1/pydantic/main.py"; Pattern = "def schema_json(";          Expect = "Present" },
    @{ Claim = "v1 does NOT have .json_schema() <-- my flagged error"; Path = "pydantic-v1/pydantic/main.py"; Pattern = "def json_schema("; Expect = "Absent" },
    @{ Claim = "v1 has .update_forward_refs()"; Path = "pydantic-v1/pydantic/main.py"; Pattern = "def update_forward_refs(";  Expect = "Present" },
    @{ Claim = "v1 has __fields__";             Path = "pydantic-v1/pydantic/main.py"; Pattern = "__fields__";                Expect = "Present" },

    # ---------- BaseModel methods: v2 side ----------
    @{ Claim = "v2 has model_dump()";           Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_dump(";           Expect = "Present" },
    @{ Claim = "v2 has model_dump_json()";      Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_dump_json(";      Expect = "Present" },
    @{ Claim = "v2 has model_validate()";       Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_validate(";       Expect = "Present" },
    @{ Claim = "v2 has model_validate_json()";  Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_validate_json(";  Expect = "Present" },
    @{ Claim = "v2 has model_construct()";      Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_construct(";      Expect = "Present" },
    @{ Claim = "v2 has model_copy()";           Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_copy(";           Expect = "Present" },
    @{ Claim = "v2 has model_json_schema()";    Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_json_schema(";    Expect = "Present" },
    @{ Claim = "v2 has model_rebuild()";        Path = "pydantic-v2/pydantic/main.py"; Pattern = "def model_rebuild(";        Expect = "Present" },
    @{ Claim = "v2 has model_fields";           Path = "pydantic-v2/pydantic/main.py"; Pattern = "model_fields";              Expect = "Present" },
    @{ Claim = "v2 main.py has NO def dict( (old name gone from BaseModel proper)"; Path = "pydantic-v2/pydantic/main.py"; Pattern = "def dict("; Expect = "Absent" },

    # ---------- RootModel / TypeAdapter ----------
    @{ Claim = "v2 has RootModel class";        Path = "pydantic-v2/pydantic/root_model.py";   Pattern = "class RootModel";   Expect = "Present" },
    @{ Claim = "v2 has TypeAdapter class";      Path = "pydantic-v2/pydantic/type_adapter.py"; Pattern = "class TypeAdapter"; Expect = "Present" },
    @{ Claim = "v1 supports __root__";          Path = "pydantic-v1/pydantic/main.py";         Pattern = "__root__";          Expect = "Present" },

    # ---------- Validators ----------
    @{ Claim = "v1 has @validator";             Path = "pydantic-v1/pydantic/class_validators.py";      Pattern = "def validator(";        Expect = "Present" },
    @{ Claim = "v1 has @root_validator";        Path = "pydantic-v1/pydantic/class_validators.py";      Pattern = "def root_validator(";   Expect = "Present" },
    @{ Claim = "v2 has @field_validator";       Path = "pydantic-v2/pydantic/functional_validators.py"; Pattern = "def field_validator(";  Expect = "Present" },
    @{ Claim = "v2 has @model_validator";       Path = "pydantic-v2/pydantic/functional_validators.py"; Pattern = "def model_validator(";  Expect = "Present" },
    @{ Claim = "v2 has @validate_call";         Path = "pydantic-v2/pydantic/validate_call_decorator.py"; Pattern = "def validate_call(";  Expect = "Present" },
    @{ Claim = "v1 has @validate_arguments";    Path = "pydantic-v1/pydantic/decorator.py";              Pattern = "def validate_arguments("; Expect = "Present" },
    @{ Claim = "v2 keeps deprecated @validator in deprecated/"; Path = "pydantic-v2/pydantic/deprecated/class_validators.py"; Pattern = "def validator("; Expect = "Present" },

    # ---------- Config keys ----------
    @{ Claim = "v1 config: allow_population_by_field_name"; Path = "pydantic-v1/pydantic/config.py"; Pattern = "allow_population_by_field_name"; Expect = "Present" },
    @{ Claim = "v1 config: anystr_lower";       Path = "pydantic-v1/pydantic/config.py"; Pattern = "anystr_lower";            Expect = "Present" },
    @{ Claim = "v1 config: anystr_strip_whitespace"; Path = "pydantic-v1/pydantic/config.py"; Pattern = "anystr_strip_whitespace"; Expect = "Present" },
    @{ Claim = "v1 config: orm_mode";           Path = "pydantic-v1/pydantic/config.py"; Pattern = "orm_mode";                Expect = "Present" },
    @{ Claim = "v1 config: schema_extra";       Path = "pydantic-v1/pydantic/config.py"; Pattern = "schema_extra";            Expect = "Present" },
    @{ Claim = "v1 config: allow_mutation";     Path = "pydantic-v1/pydantic/config.py"; Pattern = "allow_mutation";          Expect = "Present" },
    @{ Claim = "v1 config: smart_union";        Path = "pydantic-v1/pydantic/config.py"; Pattern = "smart_union";             Expect = "Present" },
    @{ Claim = "v2 config: populate_by_name";   Path = "pydantic-v2/pydantic/config.py"; Pattern = "populate_by_name";        Expect = "Present" },
    @{ Claim = "v2 config: str_to_lower";       Path = "pydantic-v2/pydantic/config.py"; Pattern = "str_to_lower";            Expect = "Present" },
    @{ Claim = "v2 config: str_strip_whitespace"; Path = "pydantic-v2/pydantic/config.py"; Pattern = "str_strip_whitespace";  Expect = "Present" },
    @{ Claim = "v2 config: from_attributes";    Path = "pydantic-v2/pydantic/config.py"; Pattern = "from_attributes";         Expect = "Present" },
    @{ Claim = "v2 config: json_schema_extra";  Path = "pydantic-v2/pydantic/config.py"; Pattern = "json_schema_extra";       Expect = "Present" },
    @{ Claim = "v2 config: validate_default";   Path = "pydantic-v2/pydantic/config.py"; Pattern = "validate_default";        Expect = "Present" },
    @{ Claim = "v2 config: frozen";             Path = "pydantic-v2/pydantic/config.py"; Pattern = "frozen";                  Expect = "Present" },
    @{ Claim = "v2 config does NOT have orm_mode key"; Path = "pydantic-v2/pydantic/config.py"; Pattern = "orm_mode";         Expect = "Absent" },

    # ---------- Field() kwargs ----------
    @{ Claim = "v1 Field: min_items";           Path = "pydantic-v1/pydantic/fields.py"; Pattern = "min_items";               Expect = "Present" },
    @{ Claim = "v1 Field: regex";               Path = "pydantic-v1/pydantic/fields.py"; Pattern = "regex";                   Expect = "Present" },
    @{ Claim = "v2 Field: pattern";             Path = "pydantic-v2/pydantic/fields.py"; Pattern = "pattern";                 Expect = "Present" },
    @{ Claim = "v2 Field: min_length";          Path = "pydantic-v2/pydantic/fields.py"; Pattern = "min_length";              Expect = "Present" },
    @{ Claim = "v2 Field: validate_default";    Path = "pydantic-v2/pydantic/fields.py"; Pattern = "validate_default";        Expect = "Present" },

    # ---------- Constrained types ----------
    @{ Claim = "v1 has ConstrainedInt";         Path = "pydantic-v1/pydantic/types.py"; Pattern = "class ConstrainedInt";     Expect = "Present" },
    @{ Claim = "v1 has ConstrainedStr";         Path = "pydantic-v1/pydantic/types.py"; Pattern = "class ConstrainedStr";     Expect = "Present" },
    @{ Claim = "v2 has StringConstraints";      Path = "pydantic-v2/pydantic/types.py"; Pattern = "StringConstraints";        Expect = "Present" },
    @{ Claim = "v2 types.py has NO ConstrainedInt class"; Path = "pydantic-v2/pydantic/types.py"; Pattern = "class ConstrainedInt"; Expect = "Absent" },

    # ---------- The to_camel / to_pascal trap ----------
    @{ Claim = "v1 utils has to_camel";         Path = "pydantic-v1/pydantic/utils.py"; Pattern = "def to_camel(";            Expect = "Present" },
    @{ Claim = "v1 utils has to_lower_camel";   Path = "pydantic-v1/pydantic/utils.py"; Pattern = "def to_lower_camel(";      Expect = "Present" },
    @{ Claim = "v2 alias_generators has to_pascal"; Path = "pydantic-v2/pydantic/alias_generators.py"; Pattern = "def to_pascal("; Expect = "Present" },
    @{ Claim = "v2 alias_generators has to_camel";  Path = "pydantic-v2/pydantic/alias_generators.py"; Pattern = "def to_camel(";  Expect = "Present" },

    # ---------- Moved / renamed types ----------
    @{ Claim = "v1 has PyObject";               Path = "pydantic-v1/pydantic/types.py"; Pattern = "PyObject";                 Expect = "Present" },
    @{ Claim = "v2 has ImportString";           Path = "pydantic-v2/pydantic/types.py"; Pattern = "ImportString";             Expect = "Present" },
    @{ Claim = "v1 has BaseSettings in-package"; Path = "pydantic-v1/pydantic/env_settings.py"; Pattern = "class BaseSettings"; Expect = "Present" },

    # ---------- Removed-outright spot checks ----------
    @{ Claim = "v1 has GenericModel";           Path = "pydantic-v1/pydantic/generics.py"; Pattern = "class GenericModel";    Expect = "Present" },
    @{ Claim = "v1 has stricturl";              Path = "pydantic-v1/pydantic/networks.py"; Pattern = "def stricturl(";        Expect = "Present" },
    @{ Claim = "v1 has ErrorWrapper";           Path = "pydantic-v1/pydantic/error_wrappers.py"; Pattern = "class ErrorWrapper"; Expect = "Present" },
    @{ Claim = "v1 errors.py has the exception zoo (MissingError)"; Path = "pydantic-v1/pydantic/errors.py"; Pattern = "class MissingError"; Expect = "Present" },
    @{ Claim = "v2 errors.py has NO MissingError class"; Path = "pydantic-v2/pydantic/errors.py"; Pattern = "class MissingError"; Expect = "Absent" }
)

$results = @()
foreach ($c in $checks) {
    $status = ""
    $detail = ""
    if (-not (Test-Path $c.Path)) {
        $status = "FILE MISSING"
        $detail = $c.Path
    }
    else {
        $hits = Select-String -Path $c.Path -Pattern $c.Pattern -SimpleMatch
        $found = ($null -ne $hits) -and (@($hits).Count -gt 0)
        if ($c.Expect -eq "Present") {
            $status = if ($found) { "PASS" } else { "FAIL" }
        }
        else {
            $status = if (-not $found) { "PASS" } else { "FAIL" }
        }
        if ($found) {
            $first = @($hits)[0]
            $detail = "line $($first.LineNumber): $($first.Line.Trim())"
            if ($detail.Length -gt 90) { $detail = $detail.Substring(0, 90) + "..." }
        }
        else {
            $detail = "not found"
        }
    }
    $results += [PSCustomObject]@{
        Status = $status
        Expect = $c.Expect
        Claim  = $c.Claim
        Detail = $detail
    }
}

$results | Format-Table -AutoSize -Wrap

$pass = @($results | Where-Object Status -eq "PASS").Count
$fail = @($results | Where-Object Status -eq "FAIL").Count
$miss = @($results | Where-Object Status -eq "FILE MISSING").Count
$summary = "SUMMARY: $pass PASS / $fail FAIL / $miss FILE MISSING (of $($results.Count) checks)"
Write-Host ""
Write-Host $summary -ForegroundColor $(if ($fail -eq 0 -and $miss -eq 0) { "Green" } else { "Yellow" })

# Save shareable report
$report = ($results | Format-Table -AutoSize -Wrap | Out-String) + "`n" + $summary
$report | Out-File -FilePath "verification-results.txt" -Encoding utf8
Write-Host "Saved to verification-results.txt"