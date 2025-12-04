"""
MCP tools for workspace management operations.
"""

import logging
from uuid import UUID
from datetime import datetime
import sys

from fastmcp import Context
from evo.common import APIConnector

from evo_mcp.context import evo_context, ensure_initialized
from evo_mcp.utils import extract_data_references


def register_workspace_tools(mcp):
    """Register all workspace-related tools with the FastMCP server."""
    
    @mcp.tool()
    async def list_my_instances(
        ctx: Context,
    ) -> list[dict]:
        """List instances the user has access to."""
        await ensure_initialized()

        if evo_context.org_id:
            await ctx.info(f"Selected instance ID {evo_context.org_id}")
        instances = await evo_context.discovery_client.list_organizations()
        return instances

    @mcp.tool()
    async def select_instance(
        instance_name: str | None = None,
        instance_id: UUID | None = None,
    ) -> dict | None:
        """Select an instance to connect to.

        Subsequent tool invocations like "list workspaces" will act on this
        Evo Instance.

        Args:
            instance_id: Instance UUID (provide either this or instance_name)
            instance_name: Instance name (provide either this or instance_id)

        Returns:
            The selected instance or `None` if no instance was matched from the
            arguments.
        """
        await ensure_initialized()

        instances = await evo_context.discovery_client.list_organizations()
        for instance in instances:
            if instance.id == instance_id or instance.display_name == instance_name:
                evo_context.org_id = instance.id
                evo_context.hub_url = instance.hubs[0].url
                evo_context.save_variables_to_cache()
                evo_context.connector = APIConnector(
                    evo_context.hub_url,
                    evo_context.connector.transport,
                    evo_context.connector._authorizer,
                )
                return instance

        return None
    

    @mcp.tool()
    async def evo_list_workspaces(
        name: str = "",
        deleted: bool = False,
        limit: int = 50
    ) -> list[dict]:
        """List workspaces with optional filtering by name or deleted status.
        
        Args:
            name: Filter by workspace name (leave empty for no filter)
            deleted: Include deleted workspaces
            limit: Maximum number of results
        """
        await ensure_initialized()
        
        workspaces = await evo_context.workspace_client.list_workspaces(
            name=name if name else None,
            deleted=deleted,
            limit=limit
        )
        
        return [
            {
                "id": str(ws.id),
                "name": ws.display_name,
                "description": ws.description,
                "user_role": ws.user_role.name if ws.user_role else None,
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
                "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
            }
            for ws in workspaces.items()
        ]

    @mcp.tool()
    async def evo_get_workspace(
        workspace_id: str = "",
        workspace_name: str = ""
    ) -> dict:
        """Get workspace details by ID or name.
        
        Args:
            workspace_id: Workspace UUID (provide either this or workspace_name)
            workspace_name: Workspace name (provide either this or workspace_id)
        """
        await ensure_initialized()
        
        if workspace_id:
            workspace = await evo_context.workspace_client.get_workspace(UUID(workspace_id))
        elif workspace_name:
            workspaces = await evo_context.workspace_client.list_workspaces(name=workspace_name)
            matching = [ws for ws in workspaces.items() if ws.display_name == workspace_name]
            if not matching:
                raise ValueError(f"Workspace '{workspace_name}' not found")
            workspace = matching[0]
        else:
            raise ValueError("Either workspace_id or workspace_name must be provided")
        
        return {
            "id": str(workspace.id),
            "name": workspace.display_name,
            "description": workspace.description,
            "user_role": workspace.user_role.name if workspace.user_role else None,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
            "created_by": workspace.created_by.id if workspace.created_by else None,
            "default_coordinate_system": workspace.default_coordinate_system,
            "labels": workspace.labels,
        }

    @mcp.tool()
    async def evo_create_workspace(
        name: str,
        description: str = "",
        labels: list[str] = []
    ) -> dict:
        """Create a new workspace.
        
        Args:
            name: Workspace name
            description: Workspace description
            labels: Workspace labels (optional list)
        """
        await ensure_initialized()
        
        workspace = await evo_context.workspace_client.create_workspace(
            name=name,
            description=description,
            labels=labels or []
        )
        
        return {
            "id": str(workspace.id),
            "name": workspace.display_name,
            "description": workspace.description,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        }

    @mcp.tool()
    async def evo_get_workspace_summary(workspace_id: str) -> dict:
        """Get summary statistics for a workspace (object counts by type).
        
        Args:
            workspace_id: Workspace UUID
        """
        await ensure_initialized()
        object_client = await evo_context.get_object_client(UUID(workspace_id))
        
        # Get all objects
        all_objects = await object_client.list_all_objects()
        
        # Count by schema type
        schema_counts = {}
        for obj in all_objects:
            schema = obj.schema_id.sub_classification
            schema_counts[schema] = schema_counts.get(schema, 0) + 1
        
        return {
            "workspace_id": str(workspace_id),
            "total_objects": len(all_objects),
            "objects_by_schema": schema_counts,
        }

    @mcp.tool()
    async def evo_health_check(workspace_id: str = "") -> dict:
        """Check health status of EVO services.
        
        Args:
            workspace_id: Workspace UUID to check object service (optional)
        """
        results = {}
        
        if evo_context.workspace_client:
            workspace_health = await evo_context.workspace_client.get_service_health()
            results["workspace_service"] = {
                "service": workspace_health.service,
                "status": workspace_health.status,
            }
        
        if workspace_id:
            await ensure_initialized()
            object_client = await evo_context.get_object_client(UUID(workspace_id))
            object_health = await object_client.get_service_health()
            results["object_service"] = {
                "service": object_health.service,
                "status": object_health.status,
            }
        
        return results


    @mcp.tool()
    async def evo_create_workspace_snapshot(
        workspace_id: str,
        snapshot_name: str = "",
        include_data_blobs: bool = False
    ) -> dict:
        """Create a snapshot of all objects and their current versions in a workspace.
        
        Args:
            workspace_id: Workspace UUID to snapshot
            snapshot_name: Optional name for the snapshot (defaults to timestamp)
            include_data_blobs: If True, include data blob references (increases size)
            
        Returns:
            Snapshot metadata and object version information
        """
        await ensure_initialized()
        object_client = await evo_context.get_object_client(UUID(workspace_id))
        workspace = await evo_context.workspace_client.get_workspace(UUID(workspace_id))
        
        # Get all objects
        all_objects = await object_client.list_all_objects()
        
        # Create snapshot
        timestamp = datetime.utcnow().isoformat()
        snapshot_name = snapshot_name or f"snapshot_{timestamp}"
        
        objects_snapshot = []
        
        for obj in all_objects:
            obj_info = {
                "id": str(obj.id),
                "name": obj.name,
                "path": obj.path,
                "schema_id": obj.schema_id.sub_classification,
                "version_id": obj.version_id,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
                # "updated_at": obj.updated_at.isoformat() if obj.updated_at else None
            }
            
            if include_data_blobs:
                try:
                    downloaded_obj = await object_client.download_object_by_id(obj.id, version=obj.version_id)
                    data_refs = extract_data_references(downloaded_obj.as_dict())
                    obj_info["data_blobs"] = data_refs
                except Exception:
                    obj_info["data_blobs"] = []
            
            objects_snapshot.append(obj_info)
        
        snapshot = {
            "snapshot_name": snapshot_name,
            "snapshot_timestamp": timestamp,
            "workspace_id": workspace_id,
            "workspace_name": workspace.display_name,
            "workspace_description": workspace.description,
            "object_count": len(objects_snapshot),
            "objects": objects_snapshot
        }
        
        return {
            "snapshot": snapshot,
            "summary": {
                "snapshot_name": snapshot_name,
                "timestamp": timestamp,
                "workspace_id": workspace_id,
                "total_objects": len(objects_snapshot),
                "note_to_user": "Store this snapshot data to restore later using evo_restore_workspace_snapshot",
                "note_to_agent": "Display the full snapshot in your response."
            }
        }
