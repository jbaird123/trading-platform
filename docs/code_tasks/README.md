# Code Tasks Documentation Structure

This directory contains all code task documentation, organized to track completion status and link related documents.

## Directory Structure

```
docs/code_tasks/
├── active/                  # Currently active/in-progress tasks
│   └── YYYY-MM-DD_feature_name.md
├── completed/               # Completed tasks, one folder per feature
│   └── YYYY-MM-DD_feature_name/
│       ├── task_list.md
│       ├── code_review.md
│       ├── implementation_findings.md (optional)
│       └── review_response.md (optional)
└── README.md               # This file
```

## Naming Conventions

### Active Tasks
- **Location**: `docs/code_tasks/active/`
- **Format**: `YYYY-MM-DD_feature_name.md`
- **Date**: Date when task was created/started
- **Example**: `2025-10-23_multi_timeframe_context.md`

### Completed Tasks
- **Location**: `docs/code_tasks/completed/YYYY-MM-DD_feature_name/`
- **Date**: Date of git commit when work was completed (last commit date)
- **Folder Contents**:
  - `task_list.md` - Original task list/plan (required)
  - `code_review.md` - Final code review document (required)
  - `implementation_findings.md` - Implementation notes/discoveries (optional)
  - `review_response.md` - Response to review feedback (optional)

## Workflow

### Starting a New Task
1. Create task file in `active/`: `docs/code_tasks/active/YYYY-MM-DD_feature_name.md`
2. Work on the implementation
3. Update task list as you progress

### Completing a Task
1. Create folder in `completed/`: `docs/code_tasks/completed/YYYY-MM-DD_feature_name/`
2. Move task file: `git mv active/YYYY-MM-DD_feature_name.md completed/YYYY-MM-DD_feature_name/task_list.md`
3. Add code review: `completed/YYYY-MM-DD_feature_name/code_review.md`
4. Add any additional documentation (findings, review responses, etc.)

## Finding Documents

### By Date
- Folder names are prefixed with completion dates (YYYY-MM-DD)
- Sort folders to see chronological order of completed work

### By Feature
- Folder names describe the feature
- All related documents (tasks, reviews, findings) are in one place

### Linking Reviews to Tasks
- Each completed folder contains both the task list and code review
- No need to search across directories

## Migration Notes

**Reorganization Date**: 2025-10-23

This structure was implemented to solve document sprawl issues:
- Previous structure mixed active and completed tasks
- Code reviews were in separate `docs/code_reviews/` directory
- No clear completion dates or task-to-review links

All historical documents have been reorganized using git commit dates to determine completion dates.
