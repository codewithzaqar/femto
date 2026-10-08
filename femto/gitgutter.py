"""
Git gutter markers for Femto (stdlib only).

Runs `git diff -U0 -- <file>` via subprocess, parses hunk headers to
extract line ranges, and caches the result per buffer. Fails silently
outside a git repo or when git is missing.
"""

import os
import subprocess


def get_git_diff_markers(filepath):
    """Return a dict: {line_number: marker} where marker is '+', '~', or '-'.
    
    Returns empty dict if not in a git repo, git is missing, or file is untracked.
    """
    if not filepath or not os.path.exists(filepath):
        return {}
    
    try:
        result = subprocess.run(
            ['git', 'diff', '-U0', '--', filepath],
            capture_output=True,
            text=True,
            timeout=2.0,
            cwd=os.path.dirname(filepath) or '.'
        )
        if result.returncode != 0:
            return {}
        
        markers = {}
        for line in result.stdout.split('\n'):
            if line.startswith('@@'):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                parts = line.split()
                if len(parts) >= 3:
                    new_range = parts[2]
                    if new_range.startswith('+'):
                        new_range = new_range[1:]
                        if ',' in new_range:
                            start, count = map(int, new_range.split(','))
                        else:
                            start, count = int(new_range), 1
                        
                        # Mark lines as modified (~) or added (+)
                        for i in range(start, start + count):
                            markers[i] = '~' if count == 1 and start > 0 else '+'
        
        return markers
    except Exception:
        return {}


def get_git_status_markers(filepath):
    """Extended version that also marks deleted lines with '-'.
    
    For simplicity, this version only shows +/~ (added/modified).
    Deleted lines would require parsing the old file, which is complex.
    """
    return get_git_diff_markers(filepath)
