library(BiocManager)

BiocManager::install(
    c(
        'limma',
        'edgeR'
    ),
    update=FALSE,
    ask=FALSE
)
