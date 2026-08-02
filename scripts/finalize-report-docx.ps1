param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [switch]$PreservePageBreaks
)

$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $document = $word.Documents.Add()
    $document.Range().InsertFile($InputPath)
    $document.PageSetup.PageWidth = $word.CentimetersToPoints(21)
    $document.PageSetup.PageHeight = $word.CentimetersToPoints(29.7)
    $document.PageSetup.TopMargin = $word.CentimetersToPoints(2.5)
    $document.PageSetup.BottomMargin = $word.CentimetersToPoints(2.5)
    $document.PageSetup.LeftMargin = $word.CentimetersToPoints(2.8)
    $document.PageSetup.RightMargin = $word.CentimetersToPoints(2.2)

    $normal = $document.Styles.Item("Normal")
    $normal.Font.Name = "Times New Roman"
    $normal.Font.Size = 12
    $normal.ParagraphFormat.Alignment = 3
    $normal.ParagraphFormat.LineSpacingRule = 5
    $normal.ParagraphFormat.LineSpacing = 15
    $normal.ParagraphFormat.SpaceAfter = 6

    foreach ($styleName in @("Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3", "Heading 4")) {
        $style = $document.Styles.Item($styleName)
        $style.Font.Name = "Times New Roman"
        $style.Font.Color = 0
    }
    $document.Styles.Item("Title").Font.Size = 20
    $document.Styles.Item("Heading 1").Font.Size = 16
    $document.Styles.Item("Heading 2").Font.Size = 14
    $document.Styles.Item("Heading 3").Font.Size = 13
    $document.Styles.Item("Heading 4").Font.Size = 12

    $document.Styles.Item("Source Code").ParagraphFormat.Alignment = 0

    foreach ($paragraph in $document.Paragraphs) {
        if ($paragraph.Range.Style.NameLocal -eq "Source Code") {
            $paragraph.Range.ParagraphFormat.Alignment = 0
        }
    }

    for ($index = 1; $index -le [Math]::Min(10, $document.Paragraphs.Count); $index++) {
        $document.Paragraphs.Item($index).Range.ParagraphFormat.Alignment = 1
    }

    foreach ($table in $document.Tables) {
        $table.Style = "Table Grid"
        $table.Range.Font.Name = "Times New Roman"
        $table.Range.Font.Size = 10
        $table.Rows.AllowBreakAcrossPages = $false
    }

    if (-not $PreservePageBreaks) {
        $headingTwoStarts = @()
        foreach ($paragraph in $document.Paragraphs) {
            if ($paragraph.Range.Style.NameLocal -eq "Heading 2") {
                $headingTwoStarts += $paragraph.Range.Start
            }
        }
        if ($headingTwoStarts.Count -ge 3) {
            $document.Range($headingTwoStarts[2], $headingTwoStarts[2]).InsertBreak(7)
            $document.Range($headingTwoStarts[1], $headingTwoStarts[1]).InsertBreak(7)
        }
    }

    $document.Repaginate()
    $pageCount = $document.ComputeStatistics(2)
    $document.SaveAs2($OutputPath, 16)
    Write-Output "Formatted DOCX saved: $OutputPath ($pageCount pages)"
    $document.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
}
