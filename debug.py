import traceback
import sys

sys.path.append('/home/ashu/Desktop/zorder')

try:
    from routes.notifications import notifications_bp
    print("Successfully imported notifications_bp")
    
    # Check if the blueprint has the decorator
    if hasattr(notifications_bp, 'before_app_first_request'):
        print("The blueprint HAS the before_app_first_request attribute")
    else:
        print("The blueprint DOES NOT HAVE the before_app_first_request attribute")
    
    # List all attributes of the blueprint
    print("\nAll attributes of notifications_bp:")
    for attr in dir(notifications_bp):
        if attr.startswith('before'):
            print(f"- {attr}")
            
    # Try importing register_notification_handlers
    try:
        from routes.notifications import register_notification_handlers
        print("\nSuccessfully imported register_notification_handlers")
        # Show its source code
        import inspect
        print("\nSource code of register_notification_handlers:")
        print(inspect.getsource(register_notification_handlers))
    except Exception as e:
        print(f"\nError importing register_notification_handlers: {e}")
    
except Exception as e:
    traceback.print_exc()
    print(f"Error: {e}") 