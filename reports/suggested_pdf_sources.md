# Дополнительные PDF под [`specs/pdf_extraction_manifest.json`](../specs/pdf_extraction_manifest.json)

Файлы кладите в **`data/raw/pdf/`** с **ровно теми именами**, что в поле **`pdf_path`** в манифесте — тогда их подхватит `resolve_pdf_path` в `extract_pdf.py`.

Для статей ниже добавлен парсинг в **`TEXT_PARSERS`** в `extract_pdf.py` (`paper_hu_fmicb_2022_alpha_helix`, `paper_melittin_processes_mdpi`).

## Frontiers Microbiology — α-helical AMP (Liu et al., doi 870361)

| | |
|---|---|
| **DOI / страница** | https://doi.org/10.3389/fmicb.2022.870361 |
| **Прямой PDF** | https://www.frontiersin.org/articles/10.3389/fmicb.2022.870361/pdf |
| **Имя в папке** | **`fmicb-13-870361.pdf`** (путь полный: `data/raw/pdf/fmicb-13-870361.pdf`; типичное имя скачанного файла с Frontiers) |

Если сохранился под другим именем — переименуйте в значение **`pdf_path`** для `paper_hu_fmicb_2022_alpha_helix` в манифесте.

## MDPI Processes — melittin-derived peptides (DOI pr14101630)

| | |
|---|---|
| **DOI / страница** | https://doi.org/10.3390/pr14101630 |
| **Прямая сборка PDF** | на странице статьи кнопка **Download PDF** (или см. **`pdf_url`** в манифесте для `paper_melittin_processes_mdpi`) |
| **Имя в папке** | **`processes-14-01630.pdf`** (`data/raw/pdf/processes-14-01630.pdf`; типичный шаблон MDPI `processes-<volume>-01630.pdf`) |

Браузер часто сохранит файл с другим именем — **переименуйте**, чтобы совпало с **`pdf_path`** для `paper_melittin_processes_mdpi` в манифесте.

---

Три уже извлекаемые работы сохранены так же по **`pdf_path`**: см. блоки `paper_ramata_stunda_2023`, `paper_zhang_2024`, `paper_lee_2023` в манифесте.
