from uuid import UUID
from evo_mcp.context import evo_context, ensure_initialized
from evo.workspaces.data import WorkspaceRole

def register_workspace_users_admin_tools(mcp):
    """Register tools for managing workspace users with the FastMCP server."""
    async def get_workspace_client():
        await ensure_initialized()
        if workspace_client := evo_context.workspace_client:
            return workspace_client
        else:
            raise ValueError("Please ensure you are connected to an instance.")
        
    @mcp.tool()
    async def get_users_in_workspace(workspace_name: str, workspace_id: UUID) -> list[dict]:
        """Get all users in the currently selected workspace.
        
        This tool will allow an admin to see:
            * who has access to the workspace,
            * who does not have access to the workspace,
            * what roles a user has in the workspace.
            
        Args:
            workspace_name: The name of the workspace to query for users. The user must provide the workspace name.
            workspace_id: The UUID of the workspace. Get UUID of the workspace from `list_workspaces` tool, match by name and use the corresponding ID.
            TODO: are there multiple workspaces with the same name? If so, we may want to remove the workspace_name argument and just use workspace_id to avoid confusion.

        Returns:
            A list of users in the workspace, their names, email addresses and roles.
        """
        workspace_client = await get_workspace_client()
        users = await workspace_client.list_user_roles(workspace_id=workspace_id)
        return [
            {
                "name": user.full_name,
                "email": user.email,
                "roles": user.role,
                "id": str(user.user_id)
            }
            for user in users
        ]
        
    @mcp.tool()
    async def add_user_to_workspace(
        workspace_name: str,
        workspace_id: UUID,
        user_email: str,
        user_id: UUID,
        role: WorkspaceRole
    ) -> dict:
        """Add a user to the currently selected workspace with a specific role.
        
        Args:
            workspace_name: The name of the workspace to add the user to. The user must provide the workspace name.
            workspace_id: The UUID of the workspace to add the user to. Get UUID of the workspace from `list_workspaces` tool, match by name and use the corresponding ID.
            user_email: The email address of the user to add to the workspace. The user of the tool is expected to provide the email address of the user to remove, 
            do not assume the email address from first name or other information. Prompt the user to provide the email address if not provided.
            user_id: The UUID of the user to add to the workspace. To get the user_id, you can use the `get_users_in_instance` tool to list all users in the instance and their corresponding IDs.
            role: The role to assign to the user in the workspace. The default role is WorkspaceRole.viewer

        Returns:
            A dictionary containing the details of the added user, including their name, email address, and assigned role.
        """
        workspace_client = await get_workspace_client()
        response = await workspace_client.assign_user_role(workspace_id=workspace_id, user_id=user_id, role=role)
        return {
            "user_email": user_email,
            "user_id": str(user_id),
            "role": response.role.name if response.role else None,
        }
        
    @mcp.tool()
    async def remove_user_from_workspace(
        workspace_name: str,
        workspace_id: UUID,
        user_email: str,
        user_id: UUID,
        role: WorkspaceRole
    ) -> dict:
        
        """Remove a user from the currently selected workspace.
        
        Args:
            workspace_name: The name of the workspace to remove the user from. The user must provide the workspace name.
            workspace_id: The UUID of the workspace to remove the user from. Get UUID of the workspace from `list_workspaces` tool, match by name and use the corresponding ID.
            user_email: The email address of the user to remove from the workspace. The user of the tool is expected to provide the email address of the user to remove, 
            do not assume the email address from first name or other information. Prompt the user to provide the email address if not provided.
            user_id: The UUID of the user to remove from the workspace. To get the user_id, you can use the `get_users_in_instance` tool to list all users in the instance and their corresponding IDs.
            role: The role to remove from the user in the workspace.

        Returns:
            A dictionary containing the details of the removed user, including their name, email address, and removed role.
        """
        
        
        workspace_client = await get_workspace_client()
        response = await workspace_client.delete_user_role(workspace_id=workspace_id, user_id=user_id)
        return {
            "Removed user": user_email
        }
        
        