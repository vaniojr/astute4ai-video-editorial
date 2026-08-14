from app.slug import slugify


def test_lowercases_and_hyphenates_spaces():
    assert slugify("Podcast 3 Irmãos") == "podcast-3-irmaos"


def test_removes_accents():
    assert slugify("Não Vou Ser Usado Pelo Centrão") == "nao-vou-ser-usado-pelo-centrao"


def test_removes_quotes_and_punctuation():
    assert slugify('Ele disse: "Isso é ótimo!"') == "ele-disse-isso-e-otimo"


def test_collapses_repeated_separators():
    assert slugify("um   --  dois") == "um-dois"


def test_handles_special_characters():
    assert slugify("100% garantido? (sim/não)") == "100-garantido-sim-nao"


def test_truncates_long_titles_without_cutting_mid_word():
    title = "Este é um título extremamente longo que ultrapassa o limite razoável de tamanho para um slug de diretório"
    slug = slugify(title, max_length=40)
    assert len(slug) <= 40
    assert not slug.endswith("-")


def test_empty_result_falls_back_to_placeholder():
    assert slugify("!!!") == "sem-titulo"
