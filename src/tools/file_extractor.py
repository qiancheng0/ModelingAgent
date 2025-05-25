import os
import zipfile
import tarfile
import gzip
import bz2
import shutil

PY7ZR_AVAILABLE = False
RARFILE_AVAILABLE = False

from .base import BaseTool

class File_Extractor_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name = "File_Extractor_Tool",
            tool_description = "Extract various compressed file formats to a folder in the original path. Supports zip, tar, tar.gz, tar.bz2, gz, bz2, rar, and 7z formats.",
            tool_version = "1.0.0",
            input_types = {
                "archive_path": "str - Path to the compressed file.",
                "extract_dir": "str - Optional, specify extraction directory. Default is None, will extract to the same directory as the compressed file.",
                "password": "str - Optional, extraction password. Default is None."
            },
            output_type = "dict - Contains success status, list of extracted files, and message.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(archive_path="workspace/example.zip")',
                    "description": "Extract a ZIP file to its original location"
                },
                {
                    "command": 'execution = tool.execute(archive_path="workspace/example.tar.gz", extract_dir="workspace/extracted")',
                    "description": "Extract a TAR.GZ file to a specified directory"
                },
                {
                    "command": 'execution = tool.execute(archive_path="workspace/protected.zip", password="secret123")',
                    "description": "Extract a password-protected ZIP file"
                }
            ],
            user_metadata = {
                "limitation": "For RAR format, system must have unrar installed. For some formats, additional Python packages may be required: py7zr for 7z files, rarfile for rar files. This tool can only process actual compressed files - if extraction fails with errors like 'File is not a zip file', the file might be a text file with incorrect extension. In that case, use File_Reader_Tool to view its content instead.",
                "best_practice": "Ensure there is sufficient disk space for extraction. If the compressed file is password-protected, provide the correct password."
            },
        )

    def execute(self, archive_path, extract_dir=None, password=None):
        """
        Extract the specified compressed file to the target directory

        Parameters:
        - archive_path: Path to the compressed file
        - extract_dir: Extraction directory, defaults to the directory of the compressed file
        - password: Optional extraction password

        Returns:
        - Dictionary containing success status, list of extracted files, and message
        """
        try:
            # Ensure correct path
            workspace_path = os.getenv("WORKSPACE_PATH")
            if "workspace" not in archive_path:
                archive_path = os.path.join(workspace_path, archive_path)
            else:
                archive_path = os.path.join(workspace_path, archive_path.split("workspace/")[-1])

            if not os.path.isfile(archive_path):
                return {
                    "success": False,
                    "message": "Error: Invalid file path."
                }
            
            # If no extraction directory is specified, use the directory of the compressed file
            if extract_dir is None:
                extract_dir = os.path.dirname(archive_path)
                # Create a subdirectory named after the compressed file (without extension)
                base_name = os.path.basename(archive_path)
                extract_folder = os.path.splitext(base_name)[0]
                # Handle multiple extensions, like .tar.gz
                if extract_folder.endswith('.tar'):
                    extract_folder = os.path.splitext(extract_folder)[0]
                extract_dir = os.path.join(extract_dir, extract_folder)
            else:
                # Process the provided extraction directory path
                if "workspace" not in extract_dir:
                    extract_dir = os.path.join(workspace_path, extract_dir)
                else:
                    extract_dir = os.path.join(workspace_path, extract_dir.split("workspace/")[-1])
            
            # Create extraction directory
            os.makedirs(extract_dir, exist_ok=True)
            
            # Get file extension
            file_ext = os.path.splitext(archive_path)[1].lower()
            file_name = os.path.basename(archive_path).lower()
            
            extracted_files = []
            
            # Call appropriate extraction method based on file format
            if file_ext == '.zip':
                extracted_files = self._extract_zip(archive_path, extract_dir, password)
            elif file_name.endswith('.tar.gz') or file_name.endswith('.tgz'):
                extracted_files = self._extract_targz(archive_path, extract_dir)
            elif file_name.endswith('.tar.bz2') or file_name.endswith('.tbz2'):
                extracted_files = self._extract_tarbz2(archive_path, extract_dir)
            elif file_ext == '.tar':
                extracted_files = self._extract_tar(archive_path, extract_dir)
            elif file_ext == '.gz':
                extracted_files = self._extract_gz(archive_path, extract_dir)
            elif file_ext == '.bz2':
                extracted_files = self._extract_bz2(archive_path, extract_dir)
            elif file_ext == '.rar':
                if not RARFILE_AVAILABLE:
                    return {
                        "success": False,
                        "message": "Error: The rarfile library is required to handle RAR files. Install with pip install rarfile, and ensure system has unrar installed."
                    }
                extracted_files = self._extract_rar(archive_path, extract_dir, password)
            elif file_ext == '.7z':
                if not PY7ZR_AVAILABLE:
                    return {
                        "success": False,
                        "message": "Error: The py7zr library is required to handle 7Z files. Install with pip install py7zr."
                    }
                extracted_files = self._extract_7z(archive_path, extract_dir, password)
            else:
                return {
                    "success": False,
                    "message": f"Error: Unsupported compression format: {file_ext}"
                }
            
            return {
                "success": True,
                "message": f"Successfully extracted files to {extract_dir}",
                "extracted_files": extracted_files
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error during extraction: {str(e)}"
            }
    
    def _extract_zip(self, archive_path, extract_dir, password=None):
        """Extract ZIP file"""
        extracted_files = []
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            # If password is provided, use it for extraction
            if password:
                zip_ref.setpassword(password.encode())
            
            # Get list of all files
            for file_info in zip_ref.infolist():
                extracted_files.append(file_info.filename)
                
            # Perform extraction
            zip_ref.extractall(extract_dir)
        return extracted_files
    
    def _extract_tar(self, archive_path, extract_dir):
        """Extract TAR file"""
        extracted_files = []
        with tarfile.open(archive_path, 'r') as tar_ref:
            # Get list of all files
            for member in tar_ref.getmembers():
                extracted_files.append(member.name)
            
            # Perform extraction
            tar_ref.extractall(extract_dir)
        return extracted_files
    
    def _extract_targz(self, archive_path, extract_dir):
        """Extract TAR.GZ file"""
        extracted_files = []
        with tarfile.open(archive_path, 'r:gz') as tar_ref:
            # Get list of all files
            for member in tar_ref.getmembers():
                extracted_files.append(member.name)
            
            # Perform extraction
            tar_ref.extractall(extract_dir)
        return extracted_files
    
    def _extract_tarbz2(self, archive_path, extract_dir):
        """Extract TAR.BZ2 file"""
        extracted_files = []
        with tarfile.open(archive_path, 'r:bz2') as tar_ref:
            # Get list of all files
            for member in tar_ref.getmembers():
                extracted_files.append(member.name)
            
            # Perform extraction
            tar_ref.extractall(extract_dir)
        return extracted_files
    
    def _extract_gz(self, archive_path, extract_dir):
        """Extract GZ file"""
        # GZ typically compresses a single file
        filename = os.path.basename(archive_path)
        if filename.endswith('.gz'):
            filename = filename[:-3]  # Remove .gz extension
        
        output_path = os.path.join(extract_dir, filename)
        
        with gzip.open(archive_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return [filename]
    
    def _extract_bz2(self, archive_path, extract_dir):
        """Extract BZ2 file"""
        # BZ2 typically compresses a single file
        filename = os.path.basename(archive_path)
        if filename.endswith('.bz2'):
            filename = filename[:-4]  # Remove .bz2 extension
        
        output_path = os.path.join(extract_dir, filename)
        
        with bz2.open(archive_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return [filename]
    
    def _extract_rar(self, archive_path, extract_dir, password=None):
        """Extract RAR file"""
        import rarfile
        
        extracted_files = []
        with rarfile.RarFile(archive_path) as rar_ref:
            # If password is provided, use it for extraction
            if password:
                rar_ref.setpassword(password)
            
            # Get list of all files
            for file_info in rar_ref.infolist():
                extracted_files.append(file_info.filename)
            
            # Perform extraction
            rar_ref.extractall(extract_dir)
        return extracted_files
    
    def _extract_7z(self, archive_path, extract_dir, password=None):
        """Extract 7Z file"""
        import py7zr
        
        extracted_files = []
        with py7zr.SevenZipFile(archive_path, mode='r', password=password) as z:
            # Get list of all files
            for file_info in z.getnames():
                extracted_files.append(file_info)
            
            # Perform extraction
            z.extractall(extract_dir)
        return extracted_files


if __name__ == "__main__":
    import json
    
    tool = File_Extractor_Tool()
    
    # Test case
    test_archive = "workspace/example.zip"
    
    try:
        execution = tool.execute(archive_path=test_archive)
        print("Extraction result:")
        print(json.dumps(execution, indent=4))
    except Exception as e:
        print(f"Execution failed: {e}")
    
    print("Done!")