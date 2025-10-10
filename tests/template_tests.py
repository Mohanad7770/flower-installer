import unittest
import jinja2
import os


class TestJinja2Templates(unittest.TestCase):
    # Ensure the template dir is found relative to project root, not tests dir
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flower_installer', 'templates')

    def setUp(self):
        loader = jinja2.FileSystemLoader(self.TEMPLATE_DIR)
        # Use StrictUndefined so missing variables raise UndefinedError
        self.env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)

    def test_flower_service_template_rendering(self):
        template = self.env.get_template('flower.service.j2')
        context = {
            'project_dir': '/opt/myproject',
            'venv': '/opt/myproject/venv',
            'redis_url': 'redis://localhost:6379/0',
            'redis_backend_url': 'redis://localhost:6379/1'
        }
        rendered = template.render(context)
        print(rendered)

        # Check that the rendered output contains expected pieces
        self.assertIn('WorkingDirectory=/opt/myproject', rendered)
        self.assertIn('ExecStart=/opt/myproject/venv/bin/celery', rendered)
        self.assertIn('--broker=redis://localhost:6379/0', rendered)
        self.assertIn(' --result-backend=redis://localhost:6379/1', rendered)

    def test_flower_service_template_rendering_no_backend_url(self):
        template = self.env.get_template('flower.service.j2')
        context = {
            'project_dir': '/opt/myproject',
            'venv': '/opt/myproject/venv',
            'redis_url': 'redis://localhost:6379/0',
            'redis_backend_url': None
        }
        rendered = template.render(context)
        print(rendered)

        # Check that the rendered output contains expected pieces
        self.assertIn('WorkingDirectory=/opt/myproject', rendered)
        self.assertIn('ExecStart=/opt/myproject/venv/bin/celery', rendered)
        self.assertIn('--broker=redis://localhost:6379/0', rendered)
        self.assertNotIn(' --result-backend=redis://localhost:6379/1', rendered)

    def test_flower_service_template_missing_variables(self):
        template = self.env.get_template('flower.service.j2')
        # Render without required variables should raise UndefinedError
        with self.assertRaises(jinja2.exceptions.UndefinedError):
            # Try to render with missing required variables
            template.render({})


if __name__ == '__main__':
    unittest.main()
