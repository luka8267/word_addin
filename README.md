# word_addin

## Test

```powershell
python -m pip install -r bunkenn\azure-static-web-apps\api\requirements.txt
python -m unittest discover -s tests -v
python -m py_compile `
  bunkenn\azure-static-web-apps\api\shared\data_access.py `
  bunkenn\azure-static-web-apps\api\shared\bunken_service.py `
  bunkenn\azure-static-web-apps\api\shared\bunken_models.py `
  bunkenn\azure-static-web-apps\api\addin_papers\__init__.py `
  bunkenn\azure-static-web-apps\api\addin_documents_sync\__init__.py
```
