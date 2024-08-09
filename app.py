import param
import panel as pn
import json
from datafed.CommandLib import API
from file_upload import file_upload_app, file_upload_app_view

pn.extension('material')

class DataFedApp(param.Parameterized):
    df_api = param.ClassSelector(class_=API, default=None)

    username = param.String(default="", label="Username")
    password = param.String(default="", label="Password")

    title = param.String(default="", label="Title")
    metadata = param.String(default="", label="Metadata (JSON format)")

    record_id = param.String(default="", label="Record ID")
    update_metadata = param.String(default="", label="Update Metadata (JSON format)")

    source_id = param.String(default="", label="Source ID")
    dest_collection = param.String(default="", label="Destination Collection")

    login_status = param.String(default="", label="Login Status")
    record_output = param.String(default="", label="Record Output")
    projects_output = param.String(default="", label="Projects Output")
    selected_project = param.String(default="", label="Selected Project")

    current_user = param.String(default="Not Logged In", label="Current User")
    current_context = param.String(default="No Context", label="Current Context")
    available_contexts = param.List(default=[], label="Available Contexts")

    selected_context = param.Selector(objects=[], label="Select Context")
    available_collections = param.List(default=[], label="Available Collections")
    selected_collection = param.Selector(objects=[], label="Select Collection")

    show_login_panel = param.Boolean(default=False)

    def __init__(self, **params):
        params['df_api'] = API()  # Initialize df_api here to avoid pickling issues
        super().__init__(**params)
        self.login_button = pn.widgets.Button(name='Login', button_type='primary')
        self.login_button.on_click(self.toggle_login_panel)
        
        self.create_button = pn.widgets.Button(name='Create Record', button_type='primary')
        self.create_button.on_click(self.create_record)
        
        self.read_button = pn.widgets.Button(name='Read Record', button_type='primary')
        self.read_button.on_click(self.read_record)
        
        self.update_button = pn.widgets.Button(name='Update Record', button_type='primary')
        self.update_button.on_click(self.update_record)
        
        self.delete_button = pn.widgets.Button(name='Delete Record', button_type='danger')
        self.delete_button.on_click(self.delete_record)
        
        self.transfer_button = pn.widgets.Button(name='Transfer Data', button_type='primary')
        self.transfer_button.on_click(self.transfer_data)
        
        self.projects_button = pn.widgets.Button(name='View Projects', button_type='primary')
        self.projects_button.on_click(self.get_projects)

        self.logout_button = pn.widgets.Button(name='Logout', button_type='warning')
        self.logout_button.on_click(self.logout)

        self.projects_json_pane = pn.pane.JSON(object=None, name='Projects Output', depth=3, width=600, height=400)
        self.metadata_json_pane = pn.pane.JSON(object=None, name='Metadata', depth=3, width=600, height=400)
        self.record_output_pane = pn.pane.Markdown("**No output yet**", name='Record Output', width=600)

        # Watch for changes in file content from FileUploadApp
        file_upload_app.param.watch(self.update_metadata_from_file_upload, 'file_content')

        self.param.watch(self.update_collections, 'selected_context')

    def toggle_login_panel(self, event):
        self.show_login_panel = True  # Set to True to open the login panel

    def check_login(self, event):
        try:
            self.df_api.loginByPassword(self.username, self.password)
            user_info = self.df_api.getAuthUser()
            if hasattr(user_info, 'username'):
                self.current_user = user_info.username
            else:
                self.current_user = str(user_info)
            self.current_context = self.df_api.getContext()
            self.available_contexts = self.get_available_contexts()
            self.param['selected_context'].objects = self.available_contexts
            self.selected_context = self.available_contexts[0] if self.available_contexts else None
            print(f"Available contexts after login: {self.available_contexts}")  # Debug print
            self.login_status = "Login Successful!"
            self.show_login_panel = False
        except Exception as e:
            self.login_status = f"Invalid username or password: {e}"

    def logout(self, event):
        self.df_api.logout()
        self.current_user = "Not Logged In"
        self.current_context = "No Context"
        self.login_status = "Logged out successfully!"
        self.username = ""
        self.password = ""

    def update_collections(self, event):
        if self.selected_context:
            collections = self.get_collections_in_context(self.selected_context)
            self.param['selected_collection'].objects = collections
            if collections:
                self.selected_collection = collections[0]
            print(f"Available collections for {self.selected_context}: {collections}")  # Debug print

    def get_collections_in_context(self, context):
        try:
            self.df_api.setContext(context)
            response = self.df_api.collectionView('root', context=context)
            print(f"Root collection details: {response}")  # Debug print
            items_list = self.df_api.collectionItemsList('root', context=context)
            collections = [item.id for item in items_list[0].item]
            print(f'collections: {collections}')
            return collections
        except Exception as e:
            return [f"Error: {e}"]

    def update_metadata_from_file_upload(self, event):
        try:
            file_content = json.loads(event.new)
            self.metadata_json_pane.object = file_content
        except json.JSONDecodeError:
            self.metadata_json_pane.object = "Invalid JSON file"

    def create_record(self, event):
        if not self.title or not file_upload_app.file_content:
            self.record_output_pane.object = pn.pane.Alert("Title and metadata are required", alert_type="danger")
            return
        try:
            if self.selected_context:
                self.df_api.setContext(self.selected_context)
            # Create record without raw data file
            response = self.df_api.dataCreate(
                title=self.title,
                metadata=file_upload_app.file_content,
                parent_id=self.selected_collection
            )
            record_id = response[0].data[0].id

            res = self.to_dict(str(response[0].data[0]))
            self.record_output_pane.object = pn.pane.Alert(f"Record created: {res}", alert_type="success")
        except Exception as e:
            self.record_output_pane.object = pn.pane.Alert(f"Failed to create record: {e}", alert_type="danger")

    def read_record(self, event):
        if not self.record_id:
            self.record_output_pane.object = pn.pane.Alert("Record ID is required", alert_type="warning")
            return
        try:
            if self.selected_context:
                self.df_api.setContext(self.selected_context)
            response = self.df_api.dataView(f"d/{self.record_id}")
            res = self.to_dict(str(response[0].data[0]))
            self.record_output_pane.object = pn.pane.Markdown(f"**Record Data:**\n\n```json\n{json.dumps(res, indent=2)}\n```")
        except Exception as e:
            self.record_output_pane.object = pn.pane.Alert(f"Failed to read record: {e}", alert_type="danger")

    def update_record(self, event):
        if not self.record_id or not self.update_metadata:
            self.record_output_pane.object = pn.pane.Alert("Record ID and metadata are required", alert_type="warning")
            return
        try:
            if self.selected_context:
                self.df_api.setContext(self.selected_context)
            response = self.df_api.dataUpdate(f"d/{self.record_id}", metadata=self.update_metadata)
            res = self.to_dict(str(response[0].data[0]))
            self.record_output_pane.object = pn.pane.Alert(f"Record updated: {res}", alert_type="success")
        except Exception as e:
            self.record_output_pane.object = pn.pane.Alert(f"Failed to update record: {e}", alert_type="danger")

    def delete_record(self, event):
        if not self.record_id:
            self.record_output_pane.object = pn.pane.Alert("Record ID is required", alert_type="warning")
            return
        try:
            if self.selected_context:
                self.df_api.setContext(self.selected_context)
            self.df_api.dataDelete(f"d/{self.record_id}")
            self.record_output_pane.object = pn.pane.Alert("Record successfully deleted", alert_type="success")
        except Exception as e:
            self.record_output_pane.object = pn.pane.Alert(f"Failed to delete record: {e}", alert_type="danger")

    def transfer_data(self, event):
        if not self.source_id or not self.dest_collection:
            self.record_output_pane.object = pn.pane.Alert("Source ID and destination collection are required", alert_type="warning")
            return
        try:
            if self.selected_context:
                self.df_api.setContext(self.selected_context)
            source_record = self.df_api.dataView(f"d/{self.source_id}")
            source_details = source_record[0].data[0]
            new_record = self.df_api.dataCreate(
                title=source_details.title,
                metadata=source_details.metadata,
                parent=self.dest_collection
            )
            new_record_id = new_record[0].data[0].id
            self.df_api.dataMove(f"d/{self.source_id}", new_record_id)
            self.record_output_pane.object = pn.pane.Alert(f"Data transferred to new record ID: {new_record_id}", alert_type="success")
        except Exception as e:
            self.record_output_pane.object = pn.pane.Alert(f"Failed to transfer data: {e}", alert_type="danger")

    def get_projects(self, event):
        try:
            response = self.df_api.projectList()
            projects = response[0].item
            projects_list = [{"id": project.id, "title": project.title} for project in projects]
            self.projects_json_pane.object = projects_list
        except Exception as e:
            self.projects_json_pane.object = {"error": str(e)}

    def get_available_contexts(self):
        try:
            response = self.df_api.projectList()
            projects = response[0].item
            return [project.id for project in projects]
        except Exception as e:
            return [f"Error: {e}"]

    def to_dict(self, data_str):
        data_dict = {}
        for line in data_str.strip().split('\n'):
            key, value = line.split(": ", 1)
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value == 'true':
                value = True
            elif value == 'false':
                value = False
            elif value.isdigit():
                value = int(value)
            data_dict[key] = value
        return data_dict

app = DataFedApp()

header = pn.Row(
    pn.layout.HSpacer(),
    pn.pane.Markdown("**User:**"),
    pn.bind(lambda current_user: pn.pane.Markdown(f"**{current_user}**"), app.param.current_user),
    pn.layout.Spacer(width=20),
    app.login_button,
    pn.layout.Spacer(width=20),
    pn.pane.Markdown("**Context:**"),
    pn.bind(lambda current_context: pn.pane.Markdown(f"**{current_context}**"), app.param.current_context),
    pn.layout.Spacer(width=20),
    app.logout_button,
    pn.layout.HSpacer()
)

login_pane = pn.Column(
    pn.Param(app.param.username),
    pn.Param(app.param.password, widgets={'password': pn.widgets.PasswordInput}),
    pn.widgets.Button(name='Submit Login', button_type='primary', on_click=app.check_login),
    pn.Param(app.param.login_status)
)

record_pane = pn.Column(
    pn.Param(app.param.selected_context, widgets={'selected_context': pn.widgets.Select}),
    pn.Param(app.param.selected_collection, widgets={'selected_collection': pn.widgets.Select}),
    pn.Tabs(
        ("Create Record", pn.Column(
            pn.Row(pn.Param(app.param.title), file_upload_app_view, app.metadata_json_pane),
            app.create_button, 
            app.record_output_pane
        )),
        ("Read Record", pn.Column(pn.Param(app.param.record_id), app.read_button, app.record_output_pane)),
        ("Update Record", pn.Column(pn.Param(app.param.record_id), pn.Param(app.param.update_metadata, widgets={'update_metadata': pn.widgets.TextAreaInput}), app.update_button, app.record_output_pane)),
        ("Delete Record", pn.Column(pn.Param(app.param.record_id), app.delete_button, app.record_output_pane)),
        ("Transfer Data", pn.Column(pn.Param(app.param.source_id), pn.Param(app.param.dest_collection), app.transfer_button, app.record_output_pane)),
    )
)

projects_pane = pn.Column(
    app.projects_button,
    app.projects_json_pane,
)

# Use MaterialTemplate for the layout
template = pn.template.MaterialTemplate(title='DataFed Management')

# Add content to the template
template.header.append(header)
template.main.append(
    pn.Tabs(
        ("Manage Records", record_pane),
        ("View Projects", projects_pane)
    )
)

# Conditionally show the login pane as a modal
template.modal.append(pn.bind(lambda show: login_pane if show else None, app.param.show_login_panel))

pn.state.onload(lambda: app.toggle_login_panel(None))  # Ensure modal can be triggered

template.servable()
