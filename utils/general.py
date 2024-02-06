def find_subject_and_content(input_string: str) -> list[str]:
    lines = input_string.split('\n')

    for i, line in enumerate(lines):
        if line.startswith('Subject:'):
            subject_line = line[len('Subject: '):]
            content = '\n'.join(lines[i + 1:])
            return subject_line, content

    # If "Subject:" is not found
    return ["", input_string]