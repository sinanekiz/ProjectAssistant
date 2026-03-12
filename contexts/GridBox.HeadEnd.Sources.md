# GridBox HeadEnd Sources

## Purpose

This file records the known source-of-truth inputs for GridBox HeadEnd context.

## Known Documentation Sources

### Documentation Space

A document export exists at:

- `C:\Users\Sinan\Downloads\GH-GridBox Headend-110326-152405.pdf`

The extracted text is sparse, but it confirms that there is a dedicated
`GridBox Headend` documentation area/space and that official documentation
exists outside the code repository.

This documentation source should be preferred over code lookup whenever it
contains the needed answer.

### Repository Documentation Folder

The HeadEnd repository also contains a `Documents` folder under:

- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.HeadEnd\Documents`

Known file example:

- `uzak bağlantı aktfileştirme.txt`

This suggests there are operational notes and field procedures that may not be
captured in application code.

## Source Priority

When answering a HeadEnd question, prefer this order:

1. context files in `ProjectAssistant\contexts`
2. official HeadEnd documentation space and exported documents
3. repository-side documentation files
4. repository code, only if behavior/ownership is still uncertain

## Why This Matters

HeadEnd is a high-operational-impact domain. The assistant should not rely on
code as the first answer source if an official operational document exists.
