import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from models import CADRequest, TaskCreateRequest, TaskUpdateRequest


DEFAULTS = {'lock_core_height': 1050, 'frame_assembly': '框套一体', 'installation_method': ''}
BASE_PARAMS = {
    'product_name': '不锈钢镀铜门', 'ys': '2号色', 'mshd': 80,
    'dhdw': '输入项测试', 'sel_kx': '右开', 'sel_nk': '内开',
    'st_val': '连体锁', 'dw': 900, 'dh': 2100,
}


class DrawingInputModelTests(unittest.TestCase):
    def test_old_params_receive_defaults_without_losing_other_fields(self):
        cad = CADRequest(**BASE_PARAMS).model_dump()
        task = TaskCreateRequest(params={**BASE_PARAMS, 'legacy_custom': '保留'}).params
        for key, value in DEFAULTS.items():
            self.assertEqual(cad.get(key), value)
            self.assertEqual(task.get(key), value)
        self.assertEqual(task['legacy_custom'], '保留')
        self.assertNotIn('lock_core_height', BASE_PARAMS)

    def test_presets_and_custom_heights_roundtrip(self):
        for height in (950, 1050, 1150, '1088.5'):
            with self.subTest(height=height):
                options = {'lock_core_height': height, 'frame_assembly': '框套分体',
                           'installation_method': '膨胀螺丝安装'}
                cad = CADRequest(**options).model_dump()
                task = TaskCreateRequest(params=options).params
                update = TaskUpdateRequest(params=options).params
                for result in (cad, task, update):
                    self.assertEqual(result.get('lock_core_height'), float(height))
                    self.assertEqual(result.get('frame_assembly'), '框套分体')
                    self.assertEqual(result.get('installation_method'), '膨胀螺丝安装')

    def test_invalid_height_is_rejected_on_all_write_models(self):
        for value in (0, -1, '', 'abc', float('nan'), float('inf')):
            for model in (CADRequest, TaskCreateRequest, TaskUpdateRequest):
                with self.subTest(value=value, model=model.__name__):
                    payload = {'lock_core_height': value}
                    with self.assertRaises(ValidationError):
                        model(**(payload if model is CADRequest else {'params': payload}))

    def test_unknown_choices_are_rejected(self):
        for key in ('frame_assembly', 'installation_method'):
            for model in (CADRequest, TaskCreateRequest, TaskUpdateRequest):
                with self.subTest(key=key, model=model.__name__):
                    payload = {key: '不支持的选项'}
                    with self.assertRaises(ValidationError):
                        model(**(payload if model is CADRequest else {'params': payload}))

    def test_state_only_update_does_not_replace_params(self):
        self.assertIsNone(TaskUpdateRequest(status='待修改').params)
        self.assertEqual(TaskUpdateRequest(params={}).params, DEFAULTS)

    def test_new_inputs_do_not_change_cad_builder_maps(self):
        from main import build_cad_params
        original = build_cad_params(CADRequest(**BASE_PARAMS))
        custom = build_cad_params(CADRequest(**BASE_PARAMS, lock_core_height=1150,
                                 frame_assembly='框套分体', installation_method='拉片安装'))
        self.assertEqual(original, custom)


class DrawingInputPersistenceTests(unittest.TestCase):
    def setUp(self):
        import main
        from database import ImageStore, TaskDatabaseManager
        from fastapi.testclient import TestClient
        self.main = main
        self.folder = tempfile.TemporaryDirectory(prefix='drawing-options-')
        root = Path(self.folder.name)
        self.database = TaskDatabaseManager(file_path=str(root / 'tasks.json'),
                          backup_dir=str(root / 'backups'), image_store=ImageStore(str(root / 'images')))
        self.database_patch = patch.object(main, 'task_db', self.database)
        self.database_patch.start()
        self.overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[main.get_current_user] = lambda: {
            'uid': 'A', 'name': '测试录入员', 'role': '录入员',
        }
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.main.app.dependency_overrides = self.overrides
        self.database_patch.stop()
        self.folder.cleanup()

    def test_create_read_update_copy_and_disk_reload_preserve_inputs(self):
        from database import TaskDatabaseManager
        values = {'lock_core_height': '1088.5', 'frame_assembly': '框套分体',
                  'installation_method': '膨胀螺丝安装'}
        response = self.client.post('/api/tasks', json={'params': {**BASE_PARAMS, **values}})
        self.assertEqual(response.status_code, 200, response.text)
        task_id = response.json()['id']
        for key, value in values.items():
            self.assertEqual(response.json()['params'][key], float(value) if key == 'lock_core_height' else value)

        changed = {**BASE_PARAMS, 'lock_core_height': 950, 'frame_assembly': '框套一体',
                   'installation_method': '拉片安装'}
        updated = self.client.put(f'/api/tasks/{task_id}', json={'params': changed})
        self.assertEqual(updated.status_code, 200, updated.text)
        latest = self.client.get(f'/api/tasks/{task_id}').json()
        self.assertEqual(latest['params'], changed)
        changes = {entry['field'] for entry in latest['history'][-1]['changes']}
        self.assertTrue(set(DEFAULTS).issubset(changes))
        copied = self.client.post(f'/api/tasks/{task_id}/copy')
        self.assertEqual(copied.status_code, 200, copied.text)
        self.assertEqual(copied.json()['params'], changed)
        reopened = TaskDatabaseManager(file_path=self.database.file_path,
                                      backup_dir=self.database.backup_dir,
                                      image_store=self.database.image_store)
        self.assertEqual(reopened.get_task(task_id)['params'], changed)
        self.assertEqual(reopened.get_task(copied.json()['id'])['params'], changed)

        state_only = self.client.put(f'/api/tasks/{task_id}', json={'status': '待修改'})
        self.assertEqual(state_only.status_code, 200, state_only.text)
        self.assertEqual(state_only.json()['params'], changed)

    def test_invalid_update_does_not_modify_persisted_task(self):
        created = self.client.post('/api/tasks', json={'params': BASE_PARAMS})
        self.assertEqual(created.status_code, 200, created.text)
        task = created.json()
        before = copy.deepcopy(self.database.get_task(task['id']))
        response = self.client.put(f"/api/tasks/{task['id']}",
                                  json={'params': {**BASE_PARAMS, 'lock_core_height': 0}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.database.get_task(task['id']), before)


if __name__ == '__main__':
    unittest.main()
