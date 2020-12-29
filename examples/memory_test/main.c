static int g_my_global_bss;
static int g_my_global_data = 37;
const int g_my_global_rodata = 45;
const int *pg_my_global_rodata = &g_my_global_rodata;
int main(void)
{
	g_my_global_bss = g_my_global_data + *pg_my_global_rodata;
	return 0;
}