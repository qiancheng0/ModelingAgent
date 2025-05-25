MULTI_TOOLS_SCHEMA = [
    {
        "name": "multi_tools_executor",
        "description": "Execute multiple tools and decide whether to complete the task",
        "parameters": {
            "type": "object",
            "properties": {
                "thinking": {
                    "type": "string",
                    "description": "Your thought process for deciding the next steps. Explain why you're choosing particular tools or approaches, what data you're looking for, and how you plan to process it."
                },
                "finish": {
                    "type": "boolean",
                    "description": "Decide whether to end the data collection for the current data point. Set to true when you have thoroughly collected the requested data. Before you set this to true, make sure you have written the report.md file."
                },
                "file_writer_tool": {
                    "type": "object",
                    "description": "File writing tool that can create new files or append to existing ones. Use this to write Python scripts for processing data, including extracting compressed files (ZIP, TAR, GZ) using Python's zipfile or tarfile modules.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path of the file to write to"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Content to write"
                                },
                                "mode": {
                                    "type": "string",
                                    "description": "Write mode: 'w' for overwrite, 'a' for append",
                                    "enum": ["w", "a"]
                                }
                            },
                            "required": ["file_path", "content", "mode"]
                        }
                    }
                },
                "file_reader_tool": {
                    "type": "object",
                    "description": "File reading tool that returns file content.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path of the file to read"
                                }
                            },
                            "required": ["file_path"]
                        }
                    }
                },
                "file_lister_tool": {
                    "type": "object",
                    "description": "List files and subdirectories in a directory.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "dir_path": {
                                    "type": "string",
                                    "description": "Directory path to list contents from"
                                }
                            },
                            "required": ["dir_path"]
                        }
                    }
                },
                "web_download_tool": {
                    "type": "object",
                    "description": "Download file from URL to specified path. After downloading, check file format. For compressed files (ZIP, TAR, etc.), use file_extractor_tool to extract the contents. For PDFs, use pdf_parser_tool for content extraction.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "URL to download from"
                                },
                                "save_path": {
                                    "type": "string",
                                    "description": "Path to save the file"
                                }
                            },
                            "required": ["url", "save_path"]
                        }
                    }
                },
                "web_search_tool": {
                    "type": "object",
                    "description": "Search the web using a search engine.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query"
                                },
                                "link": {
                                    "type": "boolean",
                                    "description": "Whether to include links"
                                },
                                "num": {
                                    "type": "integer",
                                    "description": "Number of results to return"
                                }
                            },
                            "required": ["query", "link", "num"]
                        }
                    }
                },
                "url_text_extractor_tool": {
                    "type": "object",
                    "description": "Extract text content from URL.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "URL to extract text from"
                                }
                            },
                            "required": ["url"]
                        }
                    }
                },
                "pdf_parser_tool": {
                    "type": "object",
                    "description": "Parse PDF file to extract text and images. Use this after downloading PDF files to extract structured content, tables, and text data that can be processed for modeling needs.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "pdf_path": {
                                    "type": "string",
                                    "description": "Path to the PDF file"
                                },
                                "num_pages": {
                                    "type": "integer",
                                    "description": "Number of pages to parse, -1 for all pages"
                                },
                                "min_size": {
                                    "type": "integer",
                                    "description": "Minimum size of images to save (pixels)"
                                }
                            },
                            "required": ["pdf_path", "num_pages", "min_size"]
                        }
                    }
                },
                "text_detector_tool": {
                    "type": "object",
                    "description": "Extract text from images (OCR).",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "image": {
                                    "type": "string",
                                    "description": "Path to the image file"
                                },
                                "languages": {
                                    "type": "string",
                                    "description": "OCR languages, e.g., 'en' or 'zh'"
                                },
                                "detail": {
                                    "type": "boolean",
                                    "description": "Whether to include detailed position information"
                                }
                            },
                            "required": ["image", "languages", "detail"]
                        }
                    }
                },
                "file_extractor_tool": {
                    "type": "object",
                    "description": "Extract various compressed file formats (zip, tar, tar.gz, tar.bz2, gz, bz2, rar, 7z) to a folder in the original path.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "archive_path": {
                                    "type": "string",
                                    "description": "Path to the compressed file"
                                },
                                "extract_dir": {
                                    "type": "string",
                                    "description": "Optional, specify extraction directory. Default is None, will extract to the same directory as the compressed file."
                                },
                                "password": {
                                    "type": "string",
                                    "description": "Optional, extraction password. Default is None."
                                }
                            },
                            "required": ["archive_path"]
                        }
                    }
                },
                "image_captioner_tool": {
                    "type": "object",
                    "description": "Generate description text for images.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "image": {
                                    "type": "string",
                                    "description": "Path to the image file"
                                },
                                "prompt": {
                                    "type": "string",
                                    "description": "Prompt to guide the description generation"
                                }
                            },
                            "required": ["image", "prompt"]
                        }
                    }
                },
                "python_execution_tool": {
                    "type": "object",
                    "description": "Execute Python code from a file or provided content directly. Useful for data processing, analysis, model implementation and testing.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean", 
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Optional. Path to the Python file to execute. If both file_path and code_content are provided, code_content will be written to file_path before execution."
                                },
                                "code_content": {
                                    "type": "string",
                                    "description": "Optional. Python code content to execute directly. If file_path is not provided, this will be executed from a temporary file."
                                }
                            }
                        }
                    }
                },
                "file_editor_tool": {
                    "type": "object",
                    "description": "Edit existing text files through precise operations like replacing text, inserting content before/after specific patterns, or deleting lines.",
                    "properties": {
                        "use_tool": {
                            "type": "boolean",
                            "description": "Whether to use this tool"
                        },
                        "tool_params": {
                            "type": "object",
                            "description": "Parameters for using this tool",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path of the file to edit, relative to workspace/"
                                },
                                "operation": {
                                    "type": "string",
                                    "description": "Edit operation to perform",
                                    "enum": ["replace", "insert_after", "insert_before", "delete"]
                                },
                                "target": {
                                    "type": "string",
                                    "description": "Target pattern (regex) or line number (integer) to locate in the file"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Text to insert or replace with (ignored for delete operation)"
                                },
                                "occurrence": {
                                    "type": "string",
                                    "description": "Whether to modify 'first' occurrence only (default) or 'all' occurrences",
                                    "enum": ["first", "all"]
                                }
                            },
                            "required": ["file_path", "operation", "target"]
                        }
                    }
                }
            },
            "required": ["thinking", "finish"]
        }
    }
]

